import json
from pathlib import Path
from app.service import card_service
from app.schemas import ProductInput

def run():
    base_dir = Path(__file__).resolve().parent
    
    # 1. Product 1: Манометр DM 02
    p1_path = base_dir / "data" / "product_1.json"
    with open(p1_path, "r", encoding="utf-8") as f:
        p1_data = json.load(f)
    p1_input = ProductInput.model_validate(p1_data)
    print("Generating Product 1 with live Gemini...")
    res1 = card_service.generate_product_card(p1_input)
    
    with open(base_dir / "output" / "product_1_result.json", "w", encoding="utf-8") as f:
        f.write(res1.model_dump_json(indent=2))
    with open(base_dir / "output" / "product_1_result.md", "w", encoding="utf-8") as f:
        f.write(res1.markdown_card)
        
    print(f"Product 1 Done: Title length={res1.seo_title_length}, Desc length={res1.seo_description_length}")

    # 2. Product 2: Датчик давления ОВЕН ПД100-ДИ
    p2_path = base_dir / "data" / "product_2.json"
    with open(p2_path, "r", encoding="utf-8") as f:
        p2_data = json.load(f)
    p2_input = ProductInput.model_validate(p2_data)
    print("Generating Product 2 with live Gemini...")
    res2 = card_service.generate_product_card(p2_input)
    
    with open(base_dir / "output" / "product_2_result.json", "w", encoding="utf-8") as f:
        f.write(res2.model_dump_json(indent=2))
    with open(base_dir / "output" / "product_2_result.md", "w", encoding="utf-8") as f:
        f.write(res2.markdown_card)
        
    print(f"Product 2 Done: Title length={res2.seo_title_length}, Desc length={res2.seo_description_length}")

if __name__ == "__main__":
    run()
