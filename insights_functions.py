import pandas as pd
import streamlit as st
import plotly.express as px
import ast 

def format_column(df, column_name, format_func):
    if column_name in df.columns:
        df[column_name] = df[column_name].apply(format_func)

def handle_missing_pages(df):
    if 'Number of Pages' in df.columns:
        df['Number of Pages'] = pd.to_numeric(df['Number of Pages'], errors='coerce')
        df.loc[df['Number of Pages'] == 0, 'Number of Pages'] = pd.NA

def get_all_authors(df):
    all_authors = []
    
    if 'Author' in df.columns:
        primary_authors = df['Author'].dropna().tolist()
        all_authors.extend(primary_authors)
    
    if 'Additional Authors' in df.columns:
        additional_authors = df['Additional Authors'].dropna().tolist()
        for author_string in additional_authors:
            if pd.notna(author_string) and str(author_string).strip():
                authors = [author.strip() for author in str(author_string).split(',')]
                authors = [' '.join(author.split()) for author in authors if author.strip()]
                all_authors.extend(authors)
    
    return all_authors

def get_books_by_author(df, author_name):
    primary_matches = df['Author'] == author_name if 'Author' in df.columns else pd.Series(False, index=df.index)
    
    additional_matches = pd.Series(False, index=df.index)
    if 'Additional Authors' in df.columns:
        additional_authors_clean = df['Additional Authors'].fillna('').astype(str)
        additional_matches = additional_authors_clean.str.contains(author_name, case=False, na=False)
    
    combined_matches = primary_matches | additional_matches
    return df[combined_matches]

@st.cache_data
def preprocess_data(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        if df.empty:
            st.error("The uploaded file is empty.")
            return None
            
        df.columns = df.columns.str.strip()

        required_columns = {'My Rating', 'Average Rating', 'Date Read', 'Author'}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            st.error(f"The uploaded file is missing the following required columns: {', '.join(missing_columns)}")
            return None

        df['My Rating'] = pd.to_numeric(df.get('My Rating', 0), errors='coerce')
        df.loc[df['My Rating'] == 0, 'My Rating'] = pd.NA
        df['Average Rating'] = pd.to_numeric(df.get('Average Rating'), errors='coerce')
        
        date_series = pd.to_datetime(df.get('Date Read'), errors='coerce')
        if date_series.isna().all():
            st.warning("Warning: No valid dates found in 'Date Read' column. Some features may not work properly.")
        df['Date Read'] = date_series.dt.date

        if 'Publisher' in df.columns:
            df['Publisher'] = df['Publisher'].str.title()

        handle_missing_pages(df)
        return df
        
    except Exception as e:
        st.error(f"Error processing the CSV file: {str(e)}")
        return None

@st.cache_data
def calculate_metrics(df):
    if 'Exclusive Shelf' in df.columns:
        read_df = df[df['Exclusive Shelf'].str.lower() == 'read'].copy()
    else:
        read_df = df.dropna(subset=['Date Read']).copy()

    all_authors = get_all_authors(read_df)
    unique_authors = len(set(all_authors)) if all_authors else 0

    metrics = {
        "total_books": len(read_df),
        "avg_rating": read_df['My Rating'].mean(),
        "avg_community_rating": read_df['Average Rating'].mean(),
        "total_authors": unique_authors
    }
    return read_df, metrics

@st.cache_data
def generate_books_per_year_chart(df):
    timeline = df.dropna(subset=['Date Read']).copy()
    if timeline.empty:
        return None
    timeline['Year'] = pd.to_datetime(timeline['Date Read']).dt.year.astype(int)
    books_per_year = (
        timeline.groupby('Year')
        .size()
        .reset_index(name='Books')
        .sort_values('Year')
    )
    fig = px.bar(
        books_per_year,
        x='Year',
        y='Books',
        text='Books',
        title="Books Read Each Year"
    )
    fig.update_traces(textposition='outside')
    fig.update_xaxes(type='category')
    fig.update_layout(margin=dict(t=80, b=40, l=40, r=40)) 
    return fig

@st.cache_data
def generate_top_authors_chart(df, top_n):
    all_authors = get_all_authors(df)
    
    if not all_authors:
        return None, None
    
    author_counts = pd.Series(all_authors).value_counts().reset_index()
    author_counts.columns = ['Author', 'Count']
    top_authors = author_counts.head(top_n)
    
    max_count = top_authors['Count'].max() if not top_authors.empty else 0
    y_max = max(max_count * 1.15, max_count + 1)
    
    fig = px.bar(
        top_authors,
        x='Author',
        y='Count',
        title=f"Top {top_n} Authors by Books Read (Including Co-authors)",
        text='Count',
        height=520
    )
    fig.update_traces(textposition='outside', textfont=dict(size=12), cliponaxis=False)
    fig.update_layout(
        margin=dict(t=110, b=120, l=40, r=40),
        yaxis=dict(title='Books Read', range=[0, y_max], automargin=True, tick0=0, dtick=1),
        xaxis=dict(title='Author', automargin=True)
    )
    return fig, top_authors

@st.cache_data
def generate_top_publishers_chart(df, top_n):
    if 'Publisher' not in df.columns or df['Publisher'].dropna().empty:
        return None
    top_publishers = df['Publisher'].value_counts().head(top_n).reset_index()
    top_publishers.columns = ['Publisher', 'Count']
    fig = px.bar(
        top_publishers,
        x='Publisher',
        y='Count',
        title=f"Top {top_n} Publishers by Books Read",
        text='Count',
        labels={'Publisher': 'Publisher', 'Count': 'Books Read'}
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(
        xaxis=dict(title='Publisher', automargin=True),
        margin=dict(t=80, b=40, l=40, r=40) 
    )
    return fig

@st.cache_data
def generate_binding_distribution_chart(df):
    if 'Binding' not in df.columns or df['Binding'].dropna().empty:
        return None
    binding_counts = df['Binding'].value_counts().reset_index()
    binding_counts.columns = ['Binding', 'Count']
    fig = px.pie(
        binding_counts,
        names='Binding',
        values='Count',
        title="Binding Distribution",
        labels={'Binding': 'Binding Type', 'Count': 'Books'}
    )
    return fig

@st.cache_data
def generate_books_by_year_published_chart(df):
    if 'Year Published' not in df.columns or df['Year Published'].dropna().empty:
        return None
    year_published = pd.to_numeric(df['Year Published'], errors='coerce').dropna().astype(int)
    year_counts = year_published.value_counts().reset_index()
    year_counts.columns = ['Year Published', 'Count']
    year_counts = year_counts.sort_values('Year Published')
    fig = px.bar(
        year_counts,
        x='Year Published',
        y='Count',
        title="Books Read by Year of Publication",
        text='Count',
        labels={'Year Published': 'Year', 'Count': 'Books Read'}
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(
        xaxis=dict(title='Year Published', automargin=True),
        margin=dict(t=80, b=40, l=40, r=40)
    )
    return fig

def display_metrics(metrics):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Books Read", metrics["total_books"])
    c2.metric("Your Average Rating", f"{metrics['avg_rating']:.2f}" if pd.notna(metrics['avg_rating']) else "N/A")
    c3.metric("Average Goodreads Rating", f"{metrics['avg_community_rating']:.2f}" if pd.notna(metrics['avg_community_rating']) else "N/A")
    c4.metric("Unique Authors", metrics["total_authors"])

def display_top_rated_books(df, top_n):
    top_rated = (
        df.dropna(subset=['My Rating'])
        .sort_values(by='My Rating', ascending=False)
        .head(top_n)
        [['Title', 'Author', 'My Rating', 'Average Rating', 'Date Read']]
        .reset_index(drop=True)
    )
    format_column(top_rated, 'My Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
    format_column(top_rated, 'Average Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
    st.subheader(f"Your Top {top_n} Rated Books")
    st.table(top_rated.set_index(pd.Index(range(1, len(top_rated) + 1))))

def display_longest_shortest_books(df):
    if 'Number of Pages' not in df.columns or df['Number of Pages'].isna().all():
        st.info("No data available for 'Number of Pages'.")
        return
    handle_missing_pages(df)
    valid_books = df.dropna(subset=['Number of Pages']).copy()
    valid_books['Number of Pages'] = pd.to_numeric(valid_books['Number of Pages'], errors='coerce')
    if valid_books.empty or valid_books['Number of Pages'].isna().all():
        st.info("No valid data available for 'Number of Pages'.")
        return
    longest = valid_books.nlargest(5, 'Number of Pages')[['Title', 'Author', 'Number of Pages']].reset_index(drop=True)
    shortest = valid_books.nsmallest(5, 'Number of Pages')[['Title', 'Author', 'Number of Pages']].reset_index(drop=True)
    longest['Number of Pages'] = longest['Number of Pages'].round().astype('Int64')
    shortest['Number of Pages'] = shortest['Number of Pages'].round().astype('Int64')
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Longest Books**")
        st.table(longest.set_index(pd.Index(range(1, len(longest) + 1))))
    with col2:
        st.write("**Shortest Books**")
        st.table(shortest.set_index(pd.Index(range(1, len(shortest) + 1))))

@st.cache_data
def calculate_reading_streak(df):
    if 'Date Read' not in df.columns or df['Date Read'].isna().all():
        return 0, None, None
    
    dates = pd.to_datetime(df['Date Read'].dropna()).dt.date.sort_values().unique()
    
    if len(dates) == 0:
        return 0, None, None
    elif len(dates) == 1:
        return 1, dates[0], dates[0]
    
    streak, max_streak = 1, 1
    streak_start, streak_end = dates[0], dates[0]
    max_streak_start, max_streak_end = dates[0], dates[0]
    
    for i in range(1, len(dates)):
        days_diff = (dates[i] - dates[i - 1]).days
        if days_diff == 1:
            streak += 1
            streak_end = dates[i]
            if streak > max_streak:
                max_streak = streak
                max_streak_start = streak_start
                max_streak_end = streak_end
        else:
            streak = 1
            streak_start = dates[i]
            streak_end = dates[i]
    
    return max_streak, max_streak_start, max_streak_end

@st.cache_data
def generate_cumulative_pages_chart(df):
    if 'Date Read' not in df.columns or 'Number of Pages' not in df.columns:
        return None
    pages_df = df.dropna(subset=['Date Read', 'Number of Pages']).copy()
    pages_df = pages_df.dropna(subset=['Number of Pages'])
    pages_df['Number of Pages'] = pd.to_numeric(pages_df['Number of Pages'], errors='coerce')
    pages_df['Date Read'] = pd.to_datetime(pages_df['Date Read'])
    pages_df = pages_df.sort_values('Date Read')
    pages_df['Cumulative Pages'] = pages_df['Number of Pages'].cumsum()
    fig = px.line(
        pages_df,
        x='Date Read',
        y='Cumulative Pages',
        title="Cumulative Pages Read Over Time",
        labels={'Date Read': 'Date', 'Cumulative Pages': 'Cumulative Pages'}
    )
    return fig

@st.cache_data
def calculate_average_pages_per_month(df):
    if 'Date Read' not in df.columns or 'Number of Pages' not in df.columns:
        return 0
    pages_df = df.dropna(subset=['Date Read', 'Number of Pages']).copy()
    pages_df = pages_df.dropna(subset=['Number of Pages'])
    pages_df['Number of Pages'] = pd.to_numeric(pages_df['Number of Pages'], errors='coerce')
    pages_df['YearMonth'] = pd.to_datetime(pages_df['Date Read']).dt.to_period('M')
    pages_per_month = pages_df.groupby('YearMonth')['Number of Pages'].sum()
    return pages_per_month.mean()

@st.cache_data
def calculate_total_pages_read(df):
    if 'Date Read' not in df.columns or 'Number of Pages' not in df.columns:
        return 0
    pages_df = df.dropna(subset=['Date Read', 'Number of Pages']).copy()
    pages_df = pages_df.dropna(subset=['Number of Pages'])
    pages_df['Number of Pages'] = pd.to_numeric(pages_df['Number of Pages'], errors='coerce')
    return pages_df['Number of Pages'].sum()

@st.cache_data
def calculate_average_pages_per_book(df):
    if 'Number of Pages' not in df.columns:
        return 0
    
    pages_df = df.dropna(subset=['Number of Pages']).copy()
    pages_df['Number of Pages'] = pd.to_numeric(pages_df['Number of Pages'], errors='coerce')
    pages_df = pages_df.dropna(subset=['Number of Pages'])
    
    if pages_df.empty:
        return 0
    
    total_pages = pages_df['Number of Pages'].sum()
    total_books = len(df)  
    
    if total_books == 0:
        return 0
    
    return total_pages / total_books

def display_top_books_by_goodreads_rating(df, top_n):
    top_rated_goodreads = (
        df.dropna(subset=['Average Rating'])
        .sort_values(by='Average Rating', ascending=False)
        .head(top_n)
        [['Title', 'Author', 'Average Rating', 'My Rating', 'Date Read']]
        .reset_index(drop=True)
    )
    format_column(top_rated_goodreads, 'Average Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
    format_column(top_rated_goodreads, 'My Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
    st.subheader(f"Top {top_n} Books by Goodreads Average Rating")
    st.table(top_rated_goodreads.set_index(pd.Index(range(1, len(top_rated_goodreads) + 1))))

@st.cache_data
def generate_top_genres_chart(df, top_n):
    if 'Genres' not in df.columns or df['Genres'].isna().all():
        return None
    
    all_genres = []
    for genres_list in df['Genres'].dropna():
        if isinstance(genres_list, list):
            cleaned = [str(g).strip() for g in genres_list if str(g).strip()]
            all_genres.extend(cleaned)
        elif isinstance(genres_list, str):
            s = genres_list.strip()
            parsed = None
            try:
                parsed = ast.literal_eval(s)
            except Exception:
                parsed = None

            if isinstance(parsed, list):
                cleaned = [str(g).strip() for g in parsed if str(g).strip()]
                all_genres.extend(cleaned)
            else:
                s = s.strip("[]")
                parts = [p.strip().strip("'\"") for p in s.split(',') if p.strip()]
                parts = [p for p in parts if p]  
                all_genres.extend(parts)
    
    if not all_genres:
        return None
    
    all_genres = [' '.join(g.split()) for g in all_genres]
    
    genre_counts = pd.Series(all_genres).value_counts().reset_index()
    genre_counts.columns = ['Genre', 'Count']
    top_genres = genre_counts.head(top_n)
    
    max_count = top_genres['Count'].max() if not top_genres.empty else 0
    y_max = max(max_count * 1.15, max_count + 1)
    
    fig = px.bar(
        top_genres,
        x='Genre',
        y='Count',
        title=f"Top {top_n} Genres",
        text='Count',
        height=520
    )
    fig.update_traces(textposition='outside', textfont=dict(size=12), cliponaxis=False)
    fig.update_layout(
        margin=dict(t=110, b=120, l=40, r=40),
        yaxis=dict(title='Count', range=[0, y_max], automargin=True),
        xaxis=dict(title='Genre', automargin=True)
    )
    return fig