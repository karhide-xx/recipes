const fs = require('fs');
const path = require('path');

const recipesDir = __dirname; // Adjust if your JSON files are in a subfolder

// Regex to split amount, unit, ingredient, and note
function parseIngredient(str) {
  // Example matches: "2 tbsp olive oil", "1½ cups chickpeas, rinsed and drained"
  const match = str.match(/^([\d¼½¾⅓⅔⅛⅜⅝⅞\/.,\s\-–]+)?\s*([a-zA-Z]+)?\s+([a-zA-Z\s]+?)(?:,|\s-\s)?\s*(.*)$/);
  if (match) {
    return {
      amount: match[1] ? match[1].trim() : "",
      unit: match[2] ? match[2].trim() : "",
      ingredient: match[3] ? match[3].trim() : "",
      note: match[4] ? match[4].trim() : ""
    };
  } else {
    return { amount: "", unit: "", ingredient: str.trim(), note: "" };
  }
}

// Process all .json files in the directory
fs.readdirSync(recipesDir).forEach(file => {
  if (file.endsWith('.json')) {
    const filePath = path.join(recipesDir, file);
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (Array.isArray(data.ingredients)) {
      data.ingredients = data.ingredients.map(parseIngredient);
      fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
      console.log(`Converted ingredients in ${file}`);
    }
  }
});