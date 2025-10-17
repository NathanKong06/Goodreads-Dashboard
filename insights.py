import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import timedelta

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
    primary_matches = df['Author'] == author_name if 'Author' in df.columns else pd.Series([False] * len(df))
    
    additional_matches = pd.Series([False] * len(df))
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
        read_df = df[df['Exclusive Shelf'].str.lower() == 'read']
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
def calculate_most_books_in_one_day(df):
    if 'Date Read' not in df.columns:
        return 0
    date_counts = df['Date Read'].dropna().value_counts()
    return date_counts.max() if not date_counts.empty else 0

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

def main():
    st.set_page_config(page_title="Goodreads Dashboard", layout="wide")
    st.title("Goodreads Reading Insights Dashboard")
    uploaded_file = st.file_uploader("Upload your Goodreads export CSV", type=["csv"])
    if uploaded_file is not None:
        df = preprocess_data(uploaded_file)
        if df is None:
            return  
        read_df, metrics = calculate_metrics(df)
        display_metrics(metrics)

        st.subheader("Reading Pace and Pages Insights")
        avg_pages_per_month = calculate_average_pages_per_month(read_df)
        total_pages_read = calculate_total_pages_read(read_df)
        longest_streak, streak_start, streak_end = calculate_reading_streak(read_df)
        most_books_in_one_day = calculate_most_books_in_one_day(read_df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Average Pages per Month", f"{avg_pages_per_month:.2f}" if avg_pages_per_month > 0 else "N/A")
        c2.metric("Total Pages Read", f"{int(total_pages_read):,}" if total_pages_read > 0 else "N/A")
        
        if longest_streak > 0 and streak_start and streak_end:
            if streak_start == streak_end:
                date_display = f"<br><span style='font-size: 0.8em; color: #666; line-height: 2.5;'>({streak_start.strftime('%Y-%m-%d')})</span>"
            else:
                date_display = f"<br><span style='font-size: 0.8em; color: #666; line-height: 2.5;'>({streak_start.strftime('%Y-%m-%d')} to {streak_end.strftime('%Y-%m-%d')})</span>"
            
            with c3:
                st.markdown("Longest Reading Streak")
                st.markdown(f"<div style='font-size: 2rem; font-weight: normal; margin: 0; line-height: 0.5;'>{longest_streak} days{date_display}</div>", unsafe_allow_html=True)
        else:
            c3.metric("Longest Reading Streak", "N/A")
        c4.metric("Most Books Completed in One Day", f"{most_books_in_one_day}" if most_books_in_one_day > 0 else "N/A")

        cumulative_pages_chart = generate_cumulative_pages_chart(read_df)
        if cumulative_pages_chart:
            st.plotly_chart(cumulative_pages_chart, use_container_width=True)

        st.subheader("Reading Trends")
        fig1 = generate_books_per_year_chart(read_df)
        if fig1:
            st.plotly_chart(fig1, use_container_width=True)

        st.subheader("Top Authors")
        top_n_authors = st.slider("Select the number of top authors to display:", min_value=5, max_value=20, value=10, key="top_authors_slider")
        fig2, top_authors = generate_top_authors_chart(read_df, top_n_authors)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True)
            selected_author = st.selectbox("Select an author to view their books:", top_authors['Author'], key="author_selectbox")
            author_books = get_books_by_author(read_df, selected_author)
            author_books = author_books[['Title', 'Author', 'My Rating', 'Average Rating', 'Date Read']].sort_values(by='Date Read', ascending=False).reset_index(drop=True)
            format_column(author_books, 'My Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
            format_column(author_books, 'Average Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
            st.write(f"### Books by **{selected_author}** ({len(author_books)} total)")
            st.table(author_books.set_index(pd.Index(range(1, len(author_books) + 1))))
        else:
            st.info("No author data found.")

        st.subheader("Publisher Insights")
        top_n_publishers = st.slider("Select the number of top publishers to display:", min_value=3, max_value=10, value=5, key="top_publishers_slider")
        top_publishers_chart = generate_top_publishers_chart(read_df, top_n_publishers)
        if top_publishers_chart:
            st.plotly_chart(top_publishers_chart, use_container_width=True)

        st.subheader("Binding Distribution")
        binding_distribution_chart = generate_binding_distribution_chart(read_df)
        if binding_distribution_chart:
            st.plotly_chart(binding_distribution_chart, use_container_width=True)

        st.subheader("Books Read by Year Published")
        books_by_year_published_chart = generate_books_by_year_published_chart(read_df)
        if books_by_year_published_chart:
            st.plotly_chart(books_by_year_published_chart, use_container_width=True)

        st.subheader("Your Top Rated Books")
        top_n_books = st.slider("Select the number of top-rated books to display:", min_value=5, max_value=20, value=10, key="top_rated_books_slider")
        display_top_rated_books(read_df, top_n_books)

        st.subheader("Top Books by Goodreads Average Rating")
        top_n_goodreads_books = st.slider("Select the number of top Goodreads-rated books to display:", min_value=5, max_value=20, value=10, key="goodreads_top_books_slider")
        display_top_books_by_goodreads_rating(read_df, top_n_goodreads_books)

        display_longest_shortest_books(read_df)

        with st.expander("See Raw Data"):
            display_df = read_df.copy()
            format_column(display_df, 'My Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
            format_column(display_df, 'Average Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
            st.dataframe(display_df.set_index(pd.Index(range(1, len(display_df) + 1))))
    else:
        st.info("Upload your Goodreads CSV file to see your reading insights.")

if __name__ == "__main__":
    main()
