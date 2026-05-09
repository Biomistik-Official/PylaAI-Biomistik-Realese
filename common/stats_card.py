import os
import time
from PIL import Image, ImageDraw, ImageFont
import toml

def load_stats():
    """Load and aggregate stats from local files."""
    stats = {
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "total": 0,
        "win_rate": 0.0,
        "current_brawler": "Unknown",
        "runtime": "0h 0m",
        "top_brawler": "None",
        "top_brawler_wins": 0
    }
    
    try:
        if os.path.exists("cfg/match_history.toml"):
            history = toml.load("cfg/match_history.toml")
            for brawler, data in history.items():
                if brawler != "total":
                    w = data.get("victory", 0)
                    l = data.get("defeat", 0)
                    d = data.get("draw", 0)
                    
                    stats["wins"] += w
                    stats["losses"] += l
                    stats["draws"] += d
                    
                    if w > stats["top_brawler_wins"]:
                        stats["top_brawler_wins"] = w
                        stats["top_brawler"] = brawler.title()
            
            stats["total"] = stats["wins"] + stats["losses"] + stats["draws"]
            if stats["total"] > 0:
                stats["win_rate"] = (stats["wins"] / stats["total"]) * 100
                
    except Exception as e:
        print(f"Error loading stats: {e}")
        
    return stats

def generate_stats_card(output_path="logs/stats_dashboard.png", details=None):
    stats = load_stats()
    
    if details:
        stats["current_brawler"] = details.get("brawler", stats["current_brawler"]).title()
        stats["runtime"] = details.get("runtime", stats["runtime"])
    
    # Create a clean, minimalist solid dark background
    width, height = 800, 900
    img = Image.new('RGB', (width, height), color=(18, 18, 22))
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 45)
        font_subtitle = ImageFont.truetype("arial.ttf", 25)
        font_stat_val = ImageFont.truetype("arialbd.ttf", 55)
        font_stat_lbl = ImageFont.truetype("arial.ttf", 22)
    except:
        font_title = font_subtitle = font_stat_val = font_stat_lbl = ImageFont.load_default()

    # Title Area
    draw.text((400, 70), "PYLA AUTOMATION", font=font_title, fill=(240, 240, 240), anchor="mm")
    draw.text((400, 120), "STATUS DASHBOARD", font=font_subtitle, fill=(150, 150, 170), anchor="mm")
    
    # Separator Line
    draw.line([(100, 160), (700, 160)], fill=(50, 50, 60), width=2)
    
    # Main Stats Grid (2x2)
    box_w = 320
    box_h = 160
    startX, startY = 60, 200
    gapX, gapY = 40, 40
    
    def draw_box(x, y, label, val, color):
        draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=15, fill=(30, 30, 35), outline=(50, 50, 60), width=2)
        cx = x + box_w / 2
        cy = y + box_h / 2
        draw.text((cx, cy + 10), str(val), font=font_stat_val, fill=color, anchor="mm")
        draw.text((cx, y + 35), label.upper(), font=font_stat_lbl, fill=(180, 180, 200), anchor="mm")

    # Box 1: Total Matches
    draw_box(startX, startY, "Total Matches", stats["total"], (255, 255, 255))
    
    # Box 2: Win Rate
    draw_box(startX + box_w + gapX, startY, "Win Rate", f"{stats['win_rate']:.1f}%", (100, 220, 150))
    
    # Box 3: Total Wins
    draw_box(startX, startY + box_h + gapY, "Total Wins", stats["wins"], (100, 180, 255))
    
    # Box 4: Active Brawler
    draw_box(startX + box_w + gapX, startY + box_h + gapY, "Active Brawler", stats["current_brawler"], (255, 200, 100))
    
    # Second Separator
    sec_y = startY + box_h * 2 + gapY + 50
    draw.line([(100, sec_y), (700, sec_y)], fill=(50, 50, 60), width=2)
    
    # Bottom Detailed Stats Area
    bot_y = sec_y + 40
    draw.text((400, bot_y), "PERFORMANCE INSIGHTS", font=font_subtitle, fill=(150, 150, 170), anchor="mm")
    
    draw.text((100, bot_y + 60), f"Top Brawler:  {stats['top_brawler']} ({stats['top_brawler_wins']} wins)", font=font_subtitle, fill=(220, 220, 220))
    draw.text((100, bot_y + 110), f"Session Runtime:  {stats['runtime']}", font=font_subtitle, fill=(220, 220, 220))
    draw.text((100, bot_y + 160), f"Defeats / Draws:  {stats['losses']} / {stats['draws']}", font=font_subtitle, fill=(220, 220, 220))
    
    # Footer
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    draw.text((400, height - 40), f"Generated: {current_time}", font=font_stat_lbl, fill=(100, 100, 120), anchor="mm")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    return output_path

if __name__ == "__main__":
    generate_stats_card("logs/test_dashboard.png")
    print("Generated minimalist test dashboard at logs/test_dashboard.png")
