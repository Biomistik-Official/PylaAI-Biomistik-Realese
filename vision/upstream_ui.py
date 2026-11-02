"""Versioned current-game templates from PylaAI/PylaAI 763c389 (CC BY-NC 4.0)."""
from functools import lru_cache
from pathlib import Path

import cv2


ASSET_DIR = Path(__file__).resolve().parents[1] / 'images/upstream-763c389/states'
REGIONS = {'brawler_menu_heart': (1050,0,500,110), 'brawler_menu_search': (1320,0,300,100),
           'daily_wins': (0,0,360,110), 'prestige_continue': (535,950,345,95),
           'lobby_menu': (1790,20,75,65)}


@lru_cache(maxsize=128)
def template_at(path, width, height):
    image = cv2.imread(str(path))
    if image is None:
        return None
    h,w = image.shape[:2]
    return cv2.resize(image,(max(1,round(w*width/1920)),max(1,round(h*height/1080))))


def matches(image, path, region, threshold=.95):
    height,width = image.shape[:2]
    if width < 320 or height < 180:
        return False
    x,y,w,h = region
    x0,y0 = round(x*width/1920),round(y*height/1080)
    crop = image[y0:round((y+h)*height/1080), x0:round((x+w)*width/1920)]
    template = template_at(str(path),width,height)
    if template is None or crop.shape[0] < template.shape[0] or crop.shape[1] < template.shape[1]:
        return False
    return cv2.minMaxLoc(cv2.matchTemplate(crop,template,cv2.TM_CCOEFF_NORMED))[1] > threshold


def detect_state(image):
    for name,state in [('brawler_menu_search','brawler_selection'),('brawler_menu_heart','brawler_selection'),
                       ('daily_wins','daily_wins'),('prestige_continue','prestige_milestone')]:
        if matches(image,ASSET_DIR/(name+'.png'),REGIONS[name]):
            return state
    if matches(image,ASSET_DIR/'lobby_menu.png',REGIONS['lobby_menu']):
        return 'lobby'
    return None
