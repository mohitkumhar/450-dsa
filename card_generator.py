import io
from PIL import Image, ImageDraw, ImageFont


def generate_progress_card(name, c_score, dsa_progress, current_streak, platforms):
    width, height = 800, 400
    bg_color = (24, 24, 27) # zinc-900
    card = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(card)
    
    # Attempt to load a truetype font, fallback to default if not found on OS
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 40)
        font_metric = ImageFont.truetype("arialbd.ttf", 60)
        font_label = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        try:
            # Unix-like typical font paths
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
            font_metric = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
            font_label = ImageFont.truetype("DejaVuSans.ttf", 24)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 20)
        except IOError:
            font_title = ImageFont.load_default()
            font_metric = ImageFont.load_default()
            font_label = ImageFont.load_default()
            font_small = ImageFont.load_default()
            
    text_color = (255, 255, 255)
    accent_color = (59, 130, 246) # blue-500
    
    # Draw Name
    display_name = name if name else "Anonymous"
    if len(display_name) > 20:
        display_name = display_name[:17] + "..."
    
    draw.text((40, 40), f"{display_name}'s DSA Progress", font=font_title, fill=text_color)
    
    # Draw C-Score
    draw.text((40, 130), "C-Score", font=font_label, fill=(161, 161, 170))
    draw.text((40, 165), str(c_score), font=font_metric, fill=accent_color)
    
    # Draw Progress
    draw.text((280, 130), "DSA Progress", font=font_label, fill=(161, 161, 170))
    draw.text((280, 165), f"{dsa_progress}%", font=font_metric, fill=(16, 185, 129)) # green-500
    
    # Draw Streak
    draw.text((540, 130), "Current Streak", font=font_label, fill=(161, 161, 170))
    draw.text((540, 165), f"{current_streak} \u26A1", font=font_metric, fill=(245, 158, 11)) # amber-500
    
    # Draw Platforms
    draw.text((40, 280), "Platforms:", font=font_label, fill=(161, 161, 170))
    
    plat_components = []
    if platforms.get('LeetCode', 0) > 0:
        plat_components.append(f"LeetCode: {platforms['LeetCode']}")
    if platforms.get('GFG', 0) > 0:
        plat_components.append(f"GFG: {platforms['GFG']}")
    if platforms.get('Coding Ninjas', 0) > 0:
        plat_components.append(f"Coding Ninjas: {platforms['Coding Ninjas']}")
    if platforms.get('HackerRank', 0) > 0:
        plat_components.append(f"HackerRank: {platforms['HackerRank']}")
    
    plat_str = " | ".join(plat_components)
    if not plat_str:
        plat_str = "Start solving to sync platforms!"
        
    draw.text((40, 320), plat_str, font=font_small, fill=text_color)
    
    # Branding
    draw.text((680, 350), "450-DSA", font=font_small, fill=(113, 113, 122))
    
    # Save to BytesIO
    img_io = io.BytesIO()
    card.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io
