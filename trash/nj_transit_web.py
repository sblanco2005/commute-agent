from playwright.async_api import async_playwright
import re

async def get_nj_transit_trains(limit=5):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.njtransit.com/dv-to/New%20York%20Penn%20Station", timeout=60000)
        await page.wait_for_selector("ol.list-unstyled li", timeout=20000)

        departures = await page.query_selector_all("ol.list-unstyled li")

        for i, dep in enumerate(departures):
            try:
                print(f"\n🔎 Block {i+1}:")
                block_text = await dep.inner_text()
                block_text = block_text.strip()
                print(block_text)

                time_el = await dep.query_selector("strong.h2")
                destination_el = await dep.query_selector("p strong")
                status_el = await dep.query_selector("p.h3 strong") or await dep.query_selector(".h3 strong")

                time = (await time_el.inner_text()).strip() if time_el else None
                destination = (await destination_el.inner_text()).strip() if destination_el else None
                status = (await status_el.inner_text()).strip() if status_el else "UNKNOWN"

                # Find Train ID and Line
                p_tags = await dep.query_selector_all("p")
                train_id, line = None, None
                for p in p_tags:
                    text = (await p.inner_text()).strip()
                    match = re.search(r'(NEC|NJCL)\s+Train\s+([A-Z0-9]+)', text)
                    if match:
                        line, number = match.groups()
                        train_id = f"Train {number}"
                        break

                # Track extraction from block text
                track = "?"
                if "Track" in block_text:
                    try:
                        track = block_text.split("Track")[-1].splitlines()[0].strip()
                    except:
                        pass

                print(f"  ⏰ Time: {time}")
                print(f"  📍 Destination: {destination}")
                print(f"  🚆 Train ID: {train_id}")
                print(f"  🧭 Line: {line}")
                print(f"  🛤️ Track: {track}")

                if all([time, destination, train_id, line]) and line in {"NEC", "NJCL"}:
                    # results.append(
                    #     f"🚆 {line} {train_id} to {destination} at {time} (Track {track}, {status})"
                    # )

                    results.append({
                    "line": line,
                    "train_id": train_id,
                    "destination": destination,
                    "time": time,
                    "track": track,
                    "status": status,
                })
                    if len(results) >= limit:
                        break
                else:
                    print("⚠️ Skipped: Missing one or more fields or not NEC/NJCL")

            except Exception as e:
                print(f"❌ Exception in block {i+1}: {e}")

        await browser.close()
   
    return {
    "next_trains": results,
    "delayed": any(train["status"] == "DELAYED" for train in results)
}


import asyncio

if __name__ == "__main__":
    trains = asyncio.run(get_nj_transit_trains())
    if trains:
        print("\n✅ Final Results:")
        for t in trains["next_trains"]:
            print(t)
    else:
        print("⚠️ No NEC/NJCL trains found.")