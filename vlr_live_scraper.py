import cloudscraper
from bs4 import BeautifulSoup
import json
import csv
import os
import time

# Configuration
BASE_URL = "https://www.vlr.gg"
MATCHES_URL = f"{BASE_URL}/matches"
RESULTS_URL = f"{BASE_URL}/matches/results"
PENDING_FILE = "pending_matches.json"
OUTPUT_CSV = "vlr_matches_with_odds.csv"

def load_pending():
    """Loads matches that are waiting for results."""
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_pending(pending_data):
    """Saves the waiting room data."""
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(pending_data, f, indent=4)

def get_european_proxy():
    """Fetches a free European proxy to bypass US geo-blocking on GitHub Actions."""
    print("Fetching proxy to bypass geo-blocks...")
    try:
        proxy_api_url = "https://proxylist.geonode.com/api/proxy-list?limit=10&page=1&sort_by=lastChecked&sort_type=desc&country=DE,FR,NL,GB,PL&protocols=http,https"
        resp = cloudscraper.create_scraper().get(proxy_api_url, timeout=10)
        data = resp.json()
        
        for proxy in data.get('data', []):
            if proxy.get('ip') and proxy.get('port'):
                ip_port = f"{proxy['ip']}:{proxy['port']}"
                protocol = proxy['protocols'][0]
                print(f"Using Proxy: {ip_port} ({proxy['country']})")
                return {
                    'http': f"{protocol}://{ip_port}",
                    'https': f"{protocol}://{ip_port}"
                }
    except Exception as e:
        print(f"Failed to fetch proxy: {e}. Defaulting to standard connection.")
    return None

def scrape_live_odds(scraper, pending_data, proxies):
    """Finds upcoming matches, visits individual match pages, filters for PRE-MATCH odds, and saves to queue."""
    print("\nChecking for upcoming matches...")
    try:
        response = scraper.get(MATCHES_URL, proxies=proxies, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Failed to fetch main schedule page: {e}")
        return

    match_cards = soup.find_all('a', class_=lambda c: c and 'wf-module-item' in c.split())
    
    # Inspect the next 20 matches to avoid timing out on GitHub Actions
    for card in match_cards[:20]:
        match_path = card.get('href')
        if not match_path or len(match_path.split('/')) < 3:
            continue
            
        match_id = match_path.split('/')[1]
        match_url = BASE_URL + match_path
        
        # Skip if we already captured odds for this match
        if match_id in pending_data:
            continue
            
        print(f"  Inspecting: {match_url}")
        
        try:
            match_resp = scraper.get(match_url, proxies=proxies, timeout=20)
            match_soup = BeautifulSoup(match_resp.text, 'html.parser')
            
            # 1. Team Names (wf-title-med with fallback to wf-title)
            team_names = match_soup.find_all('div', class_='wf-title-med')
            if len(team_names) < 2:
                team_names = match_soup.find_all('div', class_='wf-title')
                
            if len(team_names) < 2:
                print("    [-] Could not extract team names.")
                continue
                
            team1_name = team_names[0].text.strip()
            team2_name = team_names[1].text.strip()
            
            # 2. Extract Pre-Match Odds
            odds_containers = match_soup.find_all('a', class_=lambda c: c and 'match-bet-item' in c.split())
            team1_odds = "N/A"
            team2_odds = "N/A"
            
            if odds_containers:
                for bet_item in odds_containers:
                    item_text = bet_item.text.lower()
                    
                    # Strictly skip live odds
                    if "live" in item_text and "pre" not in item_text:
                        continue
                        
                    odds_spans = bet_item.find_all('span')
                    clean_odds = [s.text.strip() for s in odds_spans if s.text.strip().replace('.', '', 1).isdigit()]
                    
                    if len(clean_odds) >= 2:
                        team1_odds = clean_odds[0]
                        team2_odds = clean_odds[1]
                        break # Found true pre-match odds, exit loop
                        
            if team1_odds != "N/A" and team2_odds != "N/A":
                print(f"    [+] Captured Pre-Match Odds: {team1_name} ({team1_odds}) vs {team2_name} ({team2_odds})")
                pending_data[match_id] = {
                    "url": match_url,
                    "team1": team1_name,
                    "team2": team2_name,
                    "team1_odds": team1_odds,
                    "team2_odds": team2_odds,
                    "status": "pending"
                }
            else:
                print(f"    [-] No pre-match odds available for {team1_name} vs {team2_name}.")
                
            time.sleep(1.5)
            
        except Exception as e:
            print(f"    [!] Error processing {match_url}: {e}")

def process_completed_matches(scraper, pending_data):
    """Checks the results page to see if pending matches are finished, then extracts map round scores."""
    if not pending_data:
        print("\nNo pending matches waiting for results.")
        return
        
    print("\nChecking completed results...")
    try:
        response = scraper.get(RESULTS_URL, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Failed to fetch results page: {e}")
        return
    
    finished_cards = soup.find_all('a', class_=lambda c: c and 'wf-module-item' in c.split())
    finished_ids = [card.get('href').split('/')[1] for card in finished_cards if card.get('href')]
    
    completed_keys = []
    file_exists = os.path.isfile(OUTPUT_CSV)
    
    with open(OUTPUT_CSV, mode='a', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        
        if not file_exists:
            writer.writerow([
                "Match ID", "Team 1", "Team 2", "T1 Pre-Match Odds", "T2 Pre-Match Odds",
                "Map 1", "M1 Score", "Map 2", "M2 Score", 
                "Map 3", "M3 Score", "Map 4", "M4 Score", 
                "Map 5", "M5 Score", "Match URL"
            ])
            
        for match_id, data in pending_data.items():
            if match_id in finished_ids:
                print(f"  [!] Match Finished: {data['team1']} vs {data['team2']}. Scraping map scores...")
                
                try:
                    match_resp = scraper.get(data['url'], timeout=15)
                    match_soup = BeautifulSoup(match_resp.text, 'html.parser')
                    games = match_soup.find_all('div', class_='vm-stats-game')
                    
                    maps_data = []
                    for game in games:
                        if game.get('data-game-id') == 'all':
                            continue
                        
                        map_elem = game.find(class_='map')
                        map_name = map_elem.text.replace('PICK', '').strip().split('\n')[0].strip() if map_elem else "Unknown"
                        
                        score_elems = game.find_all(class_='score')
                        map_score = f"{score_elems[0].text.strip()}-{score_elems[1].text.strip()}" if len(score_elems) >= 2 else "N/A"
                        
                        if map_name and map_name not in ["Unknown", "TBD"]:
                            maps_data.append({"map": map_name, "score": map_score})
                            
                    map_columns = []
                    for i in range(5):
                        if i < len(maps_data):
                            map_columns.extend([maps_data[i]['map'], maps_data[i]['score']])
                        else:
                            map_columns.extend(["", ""])
                    
                    row = [
                        match_id, data['team1'], data['team2'], 
                        data['team1_odds'], data['team2_odds']
                    ] + map_columns + [data['url']]
                    
                    writer.writerow(row)
                    completed_keys.append(match_id)
                    time.sleep(1.5)
                    
                except Exception as e:
                    print(f"    [!] Error scraping results for {data['url']}: {e}")
                
    # Remove finished matches from queue
    for k in completed_keys:
        del pending_data[k]

def main():
    scraper = cloudscraper.create_scraper()
    pending_data = load_pending()
    
    # 1. European proxy to ensure GitHub's US servers see the odds
    proxies = get_european_proxy()
    
    # 2. Capture pre-match odds for upcoming games
    scrape_live_odds(scraper, pending_data, proxies)
    
    # 3. Harvest map round scores for finished games
    process_completed_matches(scraper, pending_data)
    
    # 4. Save queue
    save_pending(pending_data)
    
    print("\nCycle complete.")

if __name__ == "__main__":
    main()
