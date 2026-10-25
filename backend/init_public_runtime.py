"""Create a private connection configuration; never print its secret."""
import argparse,json,secrets
from pathlib import Path
from urllib.parse import urlparse
parser=argparse.ArgumentParser();parser.add_argument('--site-url',required=True);args=parser.parse_args()
url=urlparse(args.site_url)
if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ['','/']:
 parser.error('Provide your published HTTPS site origin without a path or credentials')
local=Path(__file__).resolve().parents[1]/'.local';local.mkdir(exist_ok=True);target=local/'public-runtime.json'
if target.exists():raise SystemExit('Private runtime already exists; review it before replacing the connection secret.')
target.write_text(json.dumps({'site_origin':'https://'+url.netloc.lower(),'gateway_secret':secrets.token_urlsafe(48)},indent=2),encoding='utf-8')
print('Private runtime created in .local/public-runtime.json. Configure its gateway_secret as your own Site runtime secret; do not commit this file.')
