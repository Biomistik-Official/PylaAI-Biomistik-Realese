from io import BytesIO
import os

import requests
from PIL import Image
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.utils import get_requests_proxies


brawlers_url = "https://api.brawlify.com/v1/brawlers"
brawlers_data = requests.get(brawlers_url, proxies=get_requests_proxies()).json()['list']

for brawler_obj in brawlers_data:
    icon_url = brawler_obj['imageUrl2']
    response = requests.get(icon_url, proxies=get_requests_proxies())
    image = Image.open(BytesIO(response.content))
    brawler_name = str(brawler_obj['name']).lower()
    brawler_name = os.path.basename(brawler_name).replace('.', '').replace('/', '').replace('\\', '')
    image.save(f"./assets/brawler_icons2/{brawler_name}.png")
