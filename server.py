"""US Soil Explorer: local zero-dependency proxy to USDA Soil Data Access."""
import json, os, re, time, urllib.request, urllib.parse, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent
SDA = 'https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest'
CACHE = {}
LOCK = Lock()
MAX_AGE = 6 * 3600


def query_sda(sql):
    data = urllib.parse.urlencode({'query': sql, 'format': 'JSON+COLUMNNAME'}).encode()
    req = urllib.request.Request(SDA, data=data, headers={
        'User-Agent': 'USSoilExplorer/2.0 (USDA-SSURGO research dashboard)',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': 'application/json'}, method='POST')
    last = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                payload = json.loads(response.read().decode('utf-8-sig'))
            if isinstance(payload, dict) and payload.get('Error'):
                raise RuntimeError(str(payload['Error']))
            if 'Table' not in payload:
                raise RuntimeError('USDA returned no Table: ' + str(payload)[:400])
            rows = payload['Table']
            if not rows: return []
            headers = [str(v).lower() for v in rows[0]]
            # JSON+COLUMNNAME has one header row followed by data rows.
            return [dict(zip(headers, row)) for row in rows[1:]]
        except (OSError, ValueError, RuntimeError) as exc:
            last = exc
            if attempt == 0: time.sleep(0.7)
    raise RuntimeError('USDA request failed: ' + str(last))


def cache_query(key, sql):
    with LOCK:
        entry = CACHE.get(key)
        if entry and (time.time() - entry[0]) < MAX_AGE:
            return entry[1]
    result = query_sda(sql)
    with LOCK:
        CACHE[key] = (time.time(), result)
    return result


def lookup(lat, lon):
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid latitude/longitude: expected WGS84 decimal degrees.')
    key = f'{lat:.7f},{lon:.7f}'
    # Validated numeric coordinates prevent SQL injection.
    sql = ("SELECT m.mukey, m.muname, m.musym, l.areasymbol, l.areaname "
           "FROM mapunit m JOIN legend l ON m.lkey = l.lkey "
           "WHERE m.mukey IN (SELECT * FROM "
           "SDA_Get_Mukey_from_intersection_with_WktWgs84(" 
           f"'point({lon:.7f} {lat:.7f})'))")
    units = cache_query('point:'+key, sql)
    if not units: return {'lat':lat,'lon':lon,'status':'no_map_unit','units':[],'components':[],'horizons':[]}
    mukeys = sorted({str(r['mukey']) for r in units if str(r.get('mukey','')).isdigit()})
    if not mukeys: raise RuntimeError('Unexpected map unit identifiers returned by USDA.')
    ids = ','.join(mukeys)
    sql2 = ("SELECT c.mukey, c.cokey, c.compname, c.comppct_r, c.majcompflag, "
            "c.compkind, c.drainagecl, c.taxorder, c.taxsuborder, c.taxgrtgroup, "
            "c.taxsubgrp, c.taxclname, c.taxpartsize, c.taxpartsizemod, c.taxceactcl, "
            "c.taxreaction, c.taxtempcl, c.taxmoistscl, c.taxfamother, "
            "h.chkey, h.hzname, h.hzdept_r, h.hzdepb_r, h.om_r, h.dbthirdbar_r, "
            "h.claytotal_r, h.sandtotal_r, h.silttotal_r, h.ph1to1h2o_r, h.ec_r "
            "FROM component c LEFT JOIN chorizon h ON c.cokey = h.cokey "
            f"WHERE c.mukey IN ({ids}) ORDER BY c.comppct_r DESC, c.cokey, h.hzdept_r")
    # Some columns differ with SSURGO vintage. Retry with a conservative set.
    try:
        rows = cache_query('horizons_v2:'+ids, sql2)
    except RuntimeError:
        basic = ("SELECT c.mukey, c.cokey, c.compname, c.comppct_r, c.majcompflag, "
                 "c.compkind, c.drainagecl, c.taxorder, c.taxsubgrp, c.taxclname, "
                 "h.chkey, h.hzname, h.hzdept_r, h.hzdepb_r, h.om_r, h.dbthirdbar_r, "
                 "h.claytotal_r, h.sandtotal_r, h.silttotal_r, h.ph1to1h2o_r "
                 "FROM component c LEFT JOIN chorizon h ON c.cokey = h.cokey "
                 f"WHERE c.mukey IN ({ids}) ORDER BY c.comppct_r DESC, c.cokey, h.hzdept_r")
        rows = cache_query('horizons_basic:'+ids, basic)
    components, horizons, seen = [], [], set()
    for row in rows:
        ck = str(row.get('cokey',''))
        if ck not in seen:
            components.append({k:row.get(k) for k in (
                'mukey','cokey','compname','comppct_r','majcompflag','compkind',
                'drainagecl','taxorder','taxsuborder','taxgrtgroup','taxsubgrp',
                'taxclname','taxpartsize','taxpartsizemod','taxceactcl',
                'taxreaction','taxtempcl','taxmoistscl','taxfamother')})
            seen.add(ck)
        if row.get('hzdept_r') is not None and row.get('hzdepb_r') is not None:
            horizons.append({k:row.get(k) for k in (
                'mukey','cokey','compname','chkey','hzname','hzdept_r','hzdepb_r',
                'om_r','dbthirdbar_r','claytotal_r','sandtotal_r',
                'silttotal_r','ph1to1h2o_r','ec_r')})
    # Optional SSURGO enrichment, allowing graceful fallback on incomplete surveys.
    warnings = []
    optional = [
      ('component', 'SELECT cokey, hydgrp, hydricrating, slope_r, farmlndcl, irrcapcl, nirrcapcl, runoff, mingswatertable_r FROM component WHERE mukey IN ('+ids+')'),
      ('horizon', 'SELECT h.chkey, h.awc_r, h.ksat_r, h.cec7_r, h.caco3_r, h.gypsum_r, h.sar_r, h.ec_r FROM chorizon h JOIN component c ON h.cokey=c.cokey WHERE c.mukey IN ('+ids+')'),
      ('fragments', 'SELECT f.chkey, SUM(f.fragvol_r) AS fragvol_r FROM chfrags f JOIN chorizon h ON f.chkey=h.chkey JOIN component c ON h.cokey=c.cokey WHERE c.mukey IN ('+ids+') GROUP BY f.chkey')
    ]
    for kind, q in optional:
        try:
            records = cache_query('supp_v3:'+kind+':'+ids, q)
            key = 'cokey' if kind=='component' else 'chkey'
            by_key={str(r.get(key)):r for r in records}
            for item in (components if kind=='component' else horizons):
                item.update({k:v for k,v in by_key.get(str(item.get(key)),{}).items() if k!=key})
        except Exception as exc:
            warnings.append(kind+': '+str(exc)[:140])
    return {'lat':lat,'lon':lon,'status':'ok','units':units,
            'components':components,'horizons':horizons,'supplementary_warnings':warnings,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_POST(self):
        if self.path != '/api/lookup': self.send_error(404); return
        try:
            n = int(self.headers.get('Content-Length','0'))
            if n <= 0 or n > 20000: raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(n))
            result = lookup(data['lat'], data['lon'])
            self.reply(200, result)
        except (ValueError, KeyError, TypeError) as exc: self.reply(400, {'error':str(exc)})
        except Exception as exc: self.reply(502, {'error':str(exc)})
    def reply(self, code, obj):
        data = json.dumps(obj, allow_nan=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def log_message(self, fmt, *args):
        if 'api/lookup' in str(args): print('USDA API request: ' + fmt % args)

if __name__=='__main__':
    from webbrowser import open as browser_open
    from threading import Timer
    port = int(os.environ.get('SOIL_PORT','8765'))
    print(f'\nUS Soil Explorer: http://127.0.0.1:{port}\nKeep this window open while using the dashboard. Press Ctrl+C to stop.\n')
    Timer(1, lambda:browser_open(f'http://127.0.0.1:{port}')).start()
    ThreadingHTTPServer(('127.0.0.1',port), Handler).serve_forever()
