#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json

def main():
    if len(sys.argv) != 2:
        print("Usage: python save_json_utf8.py <json_data>")
        sys.exit(1)
    
    json_data = sys.argv[1]
    
    try:
        # JSON formátum ellenőrzése
        parsed = json.loads(json_data)
        
        # UTF-8 kódolással fájlba írás
        with open('repos_response.json', 'w', encoding='utf-8') as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        
        print("JSON fájl sikeresen mentve UTF-8 kódolással")
    
    except json.JSONDecodeError as e:
        print(f"JSON parsing hiba: {e}")
        # Ha nem tudja parse-olni, akkor mint egyszerű szöveg menti
        with open('repos_response.json', 'w', encoding='utf-8') as f:
            f.write(json_data)
        print("Adat mentve szövegként UTF-8 kódolással")
    
    except Exception as e:
        print(f"Hiba: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()