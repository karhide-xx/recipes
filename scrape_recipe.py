#!/usr/bin/env python3
import sys
import os
import re
import json
import requests
import mimetypes
from recipe_scrapers import scrape_me

# Set up clean user-agent headers for downloading images
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

UNITS_LIST = [
    "g", "kg", "grams", "gram", "kilograms", "kilogram", "oz", "ounce", "ounces", "lb", "lbs", "pound", "pounds",
    "ml", "l", "cl", "dl", "litre", "litres", "liter", "liters", "cup", "cups", "tbsp", "tbs", "tablespoon", "tablespoons",
    "tsp", "teaspoon", "teaspoons", "fl oz", "fluid ounces", "fluid ounce", "pint", "pints", "quart", "quarts", "gallon", "gallons",
    "can", "cans", "tin", "tins", "pack", "packs", "package", "packages", "bag", "bags", "box", "boxes", "bunch", "bunches",
    "clove", "cloves", "head", "heads", "sprig", "sprigs", "stalk", "stalks", "slice", "slices", "pinch", "pinches", "dash", "dashes",
    "drop", "drops", "handful", "handfuls", "bulb", "bulbs", "rasher", "rashers", "piece", "pieces", "cube", "cubes"
]
# Sort units by length descending to match multi-word/longer units first
UNITS_LIST.sort(key=len, reverse=True)

def parse_ingredient(raw_str):
    raw_str = raw_str.strip()
    
    # 1. Handle special starting case: "pinch of ..."
    if raw_str.lower().startswith("pinch of "):
        ingredient = raw_str[len("pinch of "):].strip()
        # Find if there's any notes like parentheses or commas
        note = "pinch"
        paren_match = re.search(r'\(([^)]+)\)\s*$', ingredient)
        if paren_match:
            note = f"pinch, {paren_match.group(1).strip()}"
            ingredient = ingredient[:paren_match.start()].strip()
        if ',' in ingredient:
            parts = ingredient.split(',', 1)
            ingredient = parts[0].strip()
            note = f"pinch, {parts[1].strip()}"
        return {
            "amount": "",
            "unit": "",
            "ingredient": ingredient,
            "note": note
        }
        
    # 2. Extract note from ending parentheses or commas
    note = ""
    paren_match = re.search(r'\(([^)]+)\)\s*$', raw_str)
    if paren_match:
        note = paren_match.group(1).strip()
        raw_str = raw_str[:paren_match.start()].strip()
        
    if ',' in raw_str:
        parts = raw_str.split(',', 1)
        main_part = parts[0].strip()
        comma_note = parts[1].strip()
        if note:
            note = f"{comma_note} ({note})"
        else:
            note = comma_note
    else:
        main_part = raw_str
        
    # 3. Match leading amount (numbers, decimals, fractions, ranges)
    # Supported: 1, 1.5, 1/2, 1 1/2, ½, 1½, 1-2, 1 to 2, ½–¾
    # Amount Regex matches a numeric pattern:
    amount_regex = r'^((?:[0-9]+(?:\s*/\s*[0-9]+)?|[0-9]*[½⅓¼⅛⅔¾⅜⅝⅞]|[0-9]+\.[0-9]+|\.[0-9]+)(?:\s*(?:-|–|—|to)\s*(?:[0-9]+(?:\s*/\s*[0-9]+)?|[0-9]*[½⅓¼⅛⅔¾⅜⅝⅞]|[0-9]+\.[0-9]+|\.[0-9]+))?)'
    
    amount = ""
    rest = main_part
    
    amount_match = re.match(amount_regex, main_part)
    if amount_match:
        amount = amount_match.group(1).strip()
        rest = main_part[amount_match.end():].strip()
        
    # 4. Extract unit from the start of rest if it is in the units list
    unit = ""
    ingredient = rest
    
    for u in UNITS_LIST:
        # Match unit optionally followed by a period and optional trailing space/of
        pattern = r'^(' + re.escape(u) + r'\b\.?)(\s+(?:of\s+)?)?'
        unit_match = re.match(pattern, rest, re.IGNORECASE)
        if unit_match:
            unit = unit_match.group(1).lower().rstrip('.')
            ingredient = rest[unit_match.end():].strip()
            break
            
    # Clean up double spaces
    ingredient = re.sub(r'\s+', ' ', ingredient).strip()
    
    return {
        "amount": amount,
        "unit": unit,
        "ingredient": ingredient,
        "note": note
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scrape_recipe.py <recipe_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    print(f"Scraping URL: {url} ...")
    
    try:
        scraper = scrape_me(url)
    except Exception as e:
        print(f"Error: Failed to scrape URL using recipe-scrapers: {e}")
        sys.exit(1)
        
    title = scraper.title()
    print(f"Scraped Title: {title}")
    
    # 1. Determine next ID from public/recipes.json
    recipes_json_path = os.path.join("public", "recipes.json")
    recipes = []
    if os.path.exists(recipes_json_path):
        try:
            with open(recipes_json_path, "r", encoding="utf-8") as f:
                recipes = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load public/recipes.json: {e}")
            recipes = []
            
    if recipes:
        new_id = max(item.get("id", 0) for item in recipes) + 1
    else:
        new_id = 1
        
    print(f"Determined new recipe ID: {new_id}")
    
    # 2. Download and save the image
    image_url = scraper.image()
    saved_image_path = ""
    if image_url:
        print(f"Downloading image from: {image_url} ...")
        try:
            r = requests.get(image_url, headers=HEADERS, stream=True, timeout=15)
            if r.status_code == 200:
                # Guess extension
                content_type = r.headers.get("content-type", "").split(";")[0].strip()
                ext = mimetypes.guess_extension(content_type)
                if not ext:
                    _, path_ext = os.path.splitext(image_url.split("?")[0])
                    ext = path_ext if path_ext else ".jpg"
                    
                if ext == ".jpe" or ext == ".jpeg":
                    ext = ".jpg"
                elif not ext.startswith("."):
                    ext = "." + ext
                    
                image_name = f"{new_id}{ext}"
                dest_dir = os.path.join("public", "images")
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, image_name)
                
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"Saved image to: {dest_path}")
                saved_image_path = f"images/{image_name}"
            else:
                print(f"Warning: Image download failed with status code {r.status_code}")
                saved_image_path = image_url  # Fallback to remote URL
        except Exception as e:
            print(f"Warning: Failed to download image: {e}")
            saved_image_path = image_url  # Fallback to remote URL
    else:
        print("No image URL found by scraper.")
        
    # 3. Map ingredients
    ingredients_list = scraper.ingredients()
    parsed_ingredients = []
    for ing in ingredients_list:
        parsed_ingredients.append(parse_ingredient(ing))
        
    # 4. Map instructions
    # Check if instructions_list() exists, otherwise fallback to splitting by newline
    if hasattr(scraper, 'instructions_list'):
        instructions = scraper.instructions_list()
    else:
        instructions = [step.strip() for step in scraper.instructions().split('\n') if step.strip()]
        
    # Extract category and cuisine tags
    tags = []
    try:
        category = scraper.category()
        if category:
            if isinstance(category, list):
                tags.extend(category)
            else:
                tags.extend([t.strip() for t in category.split(',') if t.strip()])
    except Exception:
        pass

    try:
        cuisine = scraper.cuisine()
        if cuisine:
            if isinstance(cuisine, list):
                tags.extend(cuisine)
            else:
                tags.extend([t.strip() for t in cuisine.split(',') if t.strip()])
    except Exception:
        pass

    cleaned_tags = []
    seen = set()
    for t in tags:
        clean_t = t.lower().strip()
        if clean_t and len(clean_t) < 30 and clean_t not in seen:
            seen.add(clean_t)
            cleaned_tags.append(clean_t)

    # 5. Map recipe fields to schema
    recipe_data = {
        "title": title,
        "source": url,
        "image": saved_image_path,
        "link": url,
        "ingredients": parsed_ingredients,
        "instructions": instructions,
        "notes": [],
        "tags": cleaned_tags
    }
    
    # 6. Parse and add optional fields if available
    # Yields/serves
    try:
        yields_str = scraper.yields()
        if yields_str:
            serves_match = re.search(r'\d+', yields_str)
            if serves_match:
                recipe_data["serves"] = int(serves_match.group(0))
    except Exception:
        pass
        
    # Prep time
    try:
        prep = scraper.prep_time()
        if prep:
            recipe_data["prep_time"] = f"{prep} minutes"
    except Exception:
        pass
        
    # Cook time
    try:
        cook = scraper.cook_time()
        if cook:
            recipe_data["cook_time"] = f"{cook} minutes"
    except Exception:
        pass
        
    # 7. Write detailed JSON file
    recipes_json_dir = os.path.join("public", "recipes-json")
    os.makedirs(recipes_json_dir, exist_ok=True)
    recipe_file_path = os.path.join(recipes_json_dir, f"{new_id}.json")
    
    with open(recipe_file_path, "w", encoding="utf-8") as f:
        json.dump(recipe_data, f, indent=2, ensure_ascii=False)
    print(f"Saved recipe details to: {recipe_file_path}")
    
    # 8. Update public/recipes.json index
    recipes.append({
        "id": new_id,
        "title": title,
        "image": saved_image_path,
        "tags": cleaned_tags
    })
    
    # Sort recipes by id
    recipes.sort(key=lambda x: x.get("id", 0))
    
    with open(recipes_json_path, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)
    print(f"Updated recipe index at: {recipes_json_path}")
    print(f"Successfully imported recipe ID {new_id}!")

if __name__ == "__main__":
    main()
