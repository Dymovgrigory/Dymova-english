"""
Upload individual block files to Tilda as separate T123 blocks.
Strategy:
  - 2 existing T123 blocks: rec2421794631 (Part 1), rec2422504491 (Part 2) 
  - 2 old T123 blocks to reuse: rec2421716231, rec2421716301
  - Need 14 blocks total → create 10 new T123 blocks
  - Set content for all 14 blocks
  - Reorder blocks so they appear in the right sequence
"""
import asyncio, json, os, time, urllib.parse
from playwright.async_api import async_playwright

# Canonical block order (fixed standard, set by owner). Do not change without
# an explicit owner request. The obsolete "CTA диагностика" block was removed.
BLOCK_FILES = [
    'tilda_header_unified_min.html',      # 1  Шапка / меню
    'tilda_cta_enrollment_min.html',      # 2  Запись на новый учебный год (CTA)
    'tilda_advantages_min.html',          # 3  Наши преимущества
    'tilda_directions_min.html',          # 4  Наши направления
    'tilda_onboarding_min.html',          # 5  Как начинается обучение
    'tilda_team_min.html',                # 6  Команда
    'tilda_languages_min.html',           # 7  Другие языки
    'tilda_photobank_gallery_min.html',   # 8  Фотобанк филиалов
    'tilda_pricing_enrollment_min.html',  # 9  Запись — 3 карточки (тарифы)
    'tilda_reviews_min.html',             # 10 Отзывы (письменные + видео)
    'tilda_faq_min.html',                 # 11 FAQ
    'tilda_svedeniya_min.html',           # 12 Сведения об образовательной организации
    'tilda_contacts_map_min.html',        # 13 Контакты
    'tilda_footer_min.html',              # 14 Подвал
]

BLOCK_DIR = '/home/ubuntu/Dymova-english/prototype/tilda_blocks_min'

# These will be populated dynamically from the page
EXISTING_T123 = []

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:29229")
        context = browser.contexts[0]
        page = context.pages[0]
        
        pageid = await page.evaluate("window.pageid")
        print(f"Page ID: {pageid}")
        
        # Find all existing T123 blocks on the page
        existing = await page.evaluate("""() => {
            var records = document.querySelectorAll('.record[data-record-cod="T123"]');
            return Array.from(records).map(r => r.getAttribute('recordid'));
        }""")
        EXISTING_T123 = existing
        print(f"Found {len(EXISTING_T123)} existing T123 blocks: {EXISTING_T123}")
        
        # Read all block contents
        block_contents = []
        for bf in BLOCK_FILES:
            fpath = os.path.join(BLOCK_DIR, bf)
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            block_contents.append(content)
            print(f"  {bf}: {len(content)} chars")
        
        print(f"\nTotal blocks to upload: {len(block_contents)}")
        print(f"Existing T123 blocks to reuse: {len(EXISTING_T123)}")
        needed = max(0, len(block_contents) - len(EXISTING_T123))
        print(f"New T123 blocks to create: {needed}")
        
        # Step 1: Create new T123 blocks as needed
        all_record_ids = list(EXISTING_T123)
        
        new_blocks_needed = len(block_contents) - len(EXISTING_T123)
        last_rec_id = EXISTING_T123[-1]  # Insert after the last existing T123
        
        for i in range(new_blocks_needed):
            print(f"\nCreating T123 block {i+1}/{new_blocks_needed}...")
            result = await page.evaluate("""(afterid) => {
                return new Promise((resolve, reject) => {
                    var formData = new FormData();
                    formData.append('comm', 'addnewrecord');
                    formData.append('pageid', window.pageid);
                    formData.append('afterid', afterid);
                    formData.append('tplid', '131');
                    
                    fetch('/page/submit/', {
                        method: 'POST',
                        body: formData,
                        credentials: 'same-origin'
                    }).then(r => r.text()).then(text => {
                        try {
                            var data = JSON.parse(text);
                            // Extract record ID from the parsed JSON html field
                            var match = data.html.match(/recordid="(\d+)"/);
                            if (match) {
                                resolve({ok: true, recordid: match[1]});
                            } else {
                                resolve({ok: false, text: text.substring(0, 300)});
                            }
                        } catch(e) {
                            // Try regex on raw text  
                            var match2 = text.match(/recordid[=\\\\"]+"?(\d+)/);
                            if (match2) {
                                resolve({ok: true, recordid: match2[1]});
                            } else {
                                resolve({ok: false, error: e.message, text: text.substring(0, 300)});
                            }
                        }
                    }).catch(e => resolve({ok: false, error: e.message}));
                });
            }""", last_rec_id)
            
            if result.get('ok'):
                new_id = result['recordid']
                all_record_ids.append(new_id)
                last_rec_id = new_id
                print(f"  Created block: rec{new_id}")
            else:
                print(f"  ERROR: {result}")
                return
            
            await asyncio.sleep(1)
        
        print(f"\nAll {len(all_record_ids)} T123 block IDs: {all_record_ids}")
        
        # Step 2: Set content for each T123 block
        for idx, (rec_id, content) in enumerate(zip(all_record_ids, block_contents)):
            block_name = BLOCK_FILES[idx].replace('_min.html', '')
            print(f"\nSetting content for block {idx+1}/{len(all_record_ids)}: {block_name} (rec{rec_id}, {len(content)} chars)...")
            
            # Use the same API format as the Ace editor save
            result = await page.evaluate("""(args) => {
                var recordid = args[0];
                var code = args[1];
                return new Promise((resolve) => {
                    var formData = new FormData();
                    formData.append('comm', 'saverecord');
                    formData.append('pageid', window.pageid);
                    formData.append('recordid', recordid);
                    formData.append('onlythisfield', 'code');
                    formData.append('code', code);
                    
                    fetch('/page/submit/', {
                        method: 'POST',
                        body: formData,
                        credentials: 'same-origin'
                    }).then(r => r.text()).then(text => {
                        resolve({ok: text === 'OK', response: text.substring(0, 200)});
                    }).catch(e => resolve({ok: false, error: e.message}));
                });
            }""", [rec_id, content])
            
            if result.get('ok'):
                print(f"  OK - saved {len(content)} chars")
            else:
                print(f"  Response: {result}")
            
            await asyncio.sleep(0.5)
        
        # Step 3: Reorder blocks - put all T123 blocks at the top
        print("\nStep 3: Reordering blocks...")
        
        # Get all record IDs on the page
        all_recs = await page.evaluate("""() => {
            var records = document.querySelectorAll('.record[recordid]');
            return Array.from(records).map(r => r.getAttribute('recordid'));
        }""")
        print(f"Total records on page: {len(all_recs)}")
        
        # Build the new order: our T123 blocks first, then everything else
        our_ids = set(all_record_ids)
        other_ids = [rid for rid in all_recs if rid not in our_ids]
        new_order = all_record_ids + other_ids
        
        sort_result = await page.evaluate("""(order) => {
            return new Promise((resolve) => {
                var formData = new FormData();
                formData.append('comm', 'saverecordssort');
                formData.append('pageid', window.pageid);
                formData.append('sort', order.join(','));
                
                fetch('/page/submit/', {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin'
                }).then(r => r.text()).then(text => {
                    resolve(text.substring(0, 200));
                }).catch(e => resolve('Error: ' + e.message));
            });
        }""", new_order)
        print(f"Sort result: {sort_result}")
        
        # Step 4: Reload the page to see changes
        print("\nReloading page...")
        await page.reload(wait_until='load', timeout=60000)
        await asyncio.sleep(3)
        
        # Verify block count
        t123_count = await page.evaluate("""() => {
            var records = document.querySelectorAll('.record[data-record-cod="T123"]');
            return records.length;
        }""")
        print(f"\nT123 blocks on page: {t123_count}")
        
        print("\nDone! All blocks uploaded.")

asyncio.run(main())
