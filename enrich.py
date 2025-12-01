import pandas as pd
import time
from requests import Session, HTTPError
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, List, Optional

MAX_WORKERS = 8  
DELAY_SECONDS = 2
BASE_URL = "https://www.goodreads.com/book/show/"

s = Session()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def scrape_book_data(book_id: str) -> Tuple[str, List[str]]:
    url = f"{BASE_URL}{book_id}"
    genres: List[str] = []

    time.sleep(DELAY_SECONDS) 

    try:
        response = s.get(url, headers=HEADERS)
        response.raise_for_status() 

        soup = BeautifulSoup(response.content, 'html.parser')

        #Extract Genres
        genre_elements = soup.select('.BookPageMetadataSection__genres .BookPageMetadataSection__genreButton')
        for element in genre_elements:
            genre_text = element.get_text().strip()
            genres.append(genre_text)
        return book_id, genres

    except HTTPError as e:
        print(f"ERROR: Could not fetch book ID {book_id}. Status: {e.response.status_code}. Skipping.")
        return book_id, []
    except Exception as e:
        print(f"An unexpected error occurred for book ID {book_id}: {e}. Skipping.")
        return book_id, []

def enrich_library(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("enrich_library expects a pandas DataFrame as input")

    if 'Book Id' not in df.columns:
        return df

    df = df.copy()
    df['Book Id'] = df['Book Id'].astype(str)

    if 'Genres' not in df.columns:
        df['Genres'] = pd.NA
        need_enrich_mask = pd.Series(True, index=df.index)
    else:
        def _is_empty_genres(val):
            if pd.isna(val):
                return True
            if isinstance(val, list):
                return len(val) == 0
            if isinstance(val, str):
                s = val.strip()
                if s == "" or s == "[]":
                    return True
            return False

        need_enrich_mask = df['Genres'].apply(_is_empty_genres)

    book_ids_list = df.loc[need_enrich_mask, 'Book Id'].unique().tolist()
    book_ids_list = [id_str for id_str in book_ids_list if id_str.isdigit()]

    if not book_ids_list:
        return df

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_id = {executor.submit(scrape_book_data, book_id): book_id for book_id in book_ids_list}
        for future in as_completed(future_to_id):
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                print(exc)

    results_map = {}
    for book_id, genres in results:
        if isinstance(genres, (list, tuple)):
            results_map[book_id] = list(genres)
        elif pd.isna(genres):
            results_map[book_id] = []
        else:
            results_map[book_id] = [genres]

    if results_map:
        mask = df['Book Id'].isin(results_map.keys())
        df.loc[mask, 'Genres'] = df.loc[mask, 'Book Id'].map(results_map)

    return df