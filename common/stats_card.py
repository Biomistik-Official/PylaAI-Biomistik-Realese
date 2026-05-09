import os
import json
import time
from PIL import Image, ImageDraw, ImageFont
import toml

def load_stats():
    """Load stats from local files."""
    stats = {
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "total": 0,
        "win_rate": 0.0,
        "current_brawler": "Unknown",
        "runtime": "0h 0m"
    }
    
    try:
        # Load match history (total)
        history = toml.load("cfg/match_history.toml")
        for brawler, data in history.items():
            if brawler != "total":
                stats["wins"] += data.get("victory", 0)
                stats["losses"] += data.get("defeat", 0)
                stats["draws"] += data.get("draw", 0)
        
        stats["total"] = stats["wins"] + stats["losses"] + stats["draws"]
        if stats["total"] > 0:
            stats["win_rate"] = (stats["wins"] / stats["total"]) * 100
            
    except Exception as e:
        print(f"Error loading stats: {e}")
        
    return stats

def generate_stats_card(output_path="logs/stats_dashboard.png", details=None):
    """Generate a beautiful stats card image."""
    stats = load_stats()
    
    # Merge with real-time details if provided
    if details:
        stats["current_brawler"] = details.get("brawler", stats["current_brawler"]).title()
        stats["runtime"] = details.get("runtime", stats["runtime"])
        if "wins" in details: stats["wins"] = details["wins"]
        if "win_streak" in details: stats["win_streak"] = details["win_streak"]

    # Load background
    bg_path = "images/dashboard_bg.png"
    if not os.path.exists(bg_path):
        img = Image.new('RGB', (800, 1000), color=(20, 20, 25))
    else:
        img = Image.open(bg_path).convert('RGBA')
        img = img.resize((800, 1000), Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(img)
    
    # Load fonts
    try:
        font_main = ImageFont.truetype("arialbd.ttf", 60)
        font_sub = ImageFont.truetype("arial.ttf", 35)
        font_stat = ImageFont.truetype("arialbd.ttf", 80)
        font_label = ImageFont.truetype("arial.ttf", 25)
    except:
        font_main = font_sub = font_stat = font_label = ImageFont.load_default()

    # Draw Header
    draw.text((400, 80), "PYLA-BIOMISTIK", font=font_main, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((400, 140), "PREMIUM AUTOMATION STATUS", font=font_label, fill=(180, 180, 255, 200), anchor="mm")

    overlay = Image.new('RGBA', img.size, (0,0,0,0))
    d_overlay = ImageDraw.Draw(overlay)
    
    boxes = [
        {"rect": [50, 200, 380, 450], "label": "VICTORIES", "val": str(stats["wins"]), "color": (100, 255, 150)},
        {"rect": [420, 200, 750, 450], "label": "WIN RATE", "val": f"{stats['win_rate']:.1f}%", "color": (255, 200, 50)},
        {"rect": [50, 480, 750, 730], "label": "ACTIVE BRAWLER", "val": stats["current_brawler"], "color": (150, 200, 255)},
    ]

    for box in boxes:
        r = box["rect"]
        d_overlay.rounded_rectangle([r[0], r[1], r[2], r[3]], radius=20, fill=(255, 255, 255, 30), outline=(255, 255, 255, 50), width=2)
        cx = (r[0] + r[2]) / 2
        cy = (r[1] + r[3]) / 2
        draw.text((cx, cy + 20), box["val"], font=font_stat, fill=box["color"] + (255,), anchor="mm")
        draw.text((cx, r[1] + 40), box["label"], font=font_label, fill=(200, 200, 200, 255), anchor="mm")

    footer_y = 800
    draw.text((100, footer_y), f"Total Matches: {stats['total']}", font=font_sub, fill=(255, 255, 255, 200))
    draw.text((100, footer_y + 60), f"Runtime: {stats['runtime']}", font=font_sub, fill=(255, 255, 255, 200))
    
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    draw.text((400, 950), f"Last Updated: {current_time}", font=font_label, fill=(150, 150, 150, 150), anchor="mm")

    out = Image.alpha_composite(img, overlay)
    out = out.convert('RGB')
    
    # Ensure logs folder exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out.save(output_path, "PNG")
    return output_path
