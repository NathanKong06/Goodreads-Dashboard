import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import timedelta

def format_column(df, column_name, format_func):
    """Apply a formatting function to a column if it exists."""
    if column_name in df.columns:
        df[column_name] = df[column_name].apply(format_func)

def handle_missing_pages(df):
    """Handle missing or zero values in the 'Number of Pages' column."""
    if 'Number of Pages' in df.columns:
        df['Number of Pages'] = pd.to_numeric(df['Number of Pages'], errors='coerce')
        df.loc[df['Number of Pages'] == 0, 'Number of Pages'] = pd.NA
        df['Number of Pages'] = df['Number of Pages'].fillna("Unknown")

def get_all_authors(df):
    """Extract all authors from both 'Author' and 'Additional Authors' columns."""
    all_authors = []
    
    # Get primary authors
    if 'Author' in df.columns:
        primary_authors = df['Author'].dropna().tolist()
        all_authors.extend(primary_authors)
    
    # Get additional authors
    if 'Additional Authors' in df.columns:
        additional_authors = df['Additional Authors'].dropna().tolist()
        for author_string in additional_authors:
            if pd.notna(author_string) and str(author_string).strip():
                # Split by comma and clean up each author name
                authors = [author.strip() for author in str(author_string).split(',')]
                # Remove empty strings and normalize multiple spaces
                authors = [' '.join(author.split()) for author in authors if author.strip()]
                all_authors.extend(authors)
    
    return all_authors

def get_books_by_author(df, author_name):
    """Get books where the specified author appears in either 'Author' or 'Additional Authors' columns."""
    # Check primary author column
    primary_matches = df['Author'] == author_name if 'Author' in df.columns else pd.Series([False] * len(df))
    
    # Check additional authors column
    additional_matches = pd.Series([False] * len(df))
    if 'Additional Authors' in df.columns:
        for idx, additional_authors in df['Additional Authors'].items():
            if pd.notna(additional_authors) and str(additional_authors).strip():
                # Split and clean additional authors
                authors = [author.strip() for author in str(additional_authors).split(',')]
                authors = [' '.join(author.split()) for author in authors if author.strip()]
                if author_name in authors:
                    additional_matches.iloc[idx] = True
    
    # Combine both conditions
    combined_matches = primary_matches | additional_matches
    return df[combined_matches]

@st.cache_data
def preprocess_data(uploaded_file):
    """Preprocess the uploaded Goodreads CSV file."""
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()

    required_columns = {'My Rating', 'Average Rating', 'Date Read', 'Author'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        st.error(f"The uploaded file is missing the following required columns: {', '.join(missing_columns)}")
        return None

    df['My Rating'] = pd.to_numeric(df.get('My Rating', 0), errors='coerce')
    df.loc[df['My Rating'] == 0, 'My Rating'] = pd.NA
    df['Average Rating'] = pd.to_numeric(df.get('Average Rating'), errors='coerce')
    df['Date Read'] = pd.to_datetime(df.get('Date Read'), errors='coerce').dt.date

    if 'Publisher' in df.columns:
        df['Publisher'] = df['Publisher'].str.title()

    handle_missing_pages(df)
    return df

@st.cache_data
def calculate_metrics(df):
    """Calculate key metrics from the data."""
    if 'Exclusive Shelf' in df.columns:
        read_df = df[df['Exclusive Shelf'].str.lower() == 'read']
    else:
        read_df = df.dropna(subset=['Date Read']).copy()

    # Calculate unique authors including additional authors
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
    """Generate a bar chart for books read per year."""
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
    """Generate a bar chart for top authors including additional authors."""
    # Get all authors from both columns
    all_authors = get_all_authors(df)
    
    if not all_authors:
        return None, None
    
    # Count author occurrences
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
    """Generate a bar chart for top publishers."""
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
    """Generate a pie chart for binding distribution."""
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
    """Generate a bar chart for books read by year published."""
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
    """Display key metrics in Streamlit columns."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Books Read", metrics["total_books"])
    c2.metric("Your Avgerage Rating", f"{metrics['avg_rating']:.2f}" if pd.notna(metrics['avg_rating']) else "N/A")
    c3.metric("Average Goodreads Rating", f"{metrics['avg_community_rating']:.2f}" if pd.notna(metrics['avg_community_rating']) else "N/A")
    c4.metric("Unique Authors", metrics["total_authors"])

def display_top_rated_books(df, top_n):
    """Display the top-rated books."""
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
    """Display the longest and shortest books."""
    if 'Number of Pages' not in df.columns or df['Number of Pages'].isna().all():
        st.info("No data available for 'Number of Pages'.")
        return
    handle_missing_pages(df)
    valid_books = df[df['Number of Pages'] != "Unknown"].copy()
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
    """Calculate the longest reading streak (consecutive days with books read)."""
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
    """Generate a line chart for cumulative pages read over time."""
    if 'Date Read' not in df.columns or 'Number of Pages' not in df.columns:
        return None
    pages_df = df.dropna(subset=['Date Read', 'Number of Pages']).copy()
    pages_df = pages_df[pages_df['Number of Pages'] != "Unknown"]
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
    """Calculate the average number of pages read per month."""
    if 'Date Read' not in df.columns or 'Number of Pages' not in df.columns:
        return 0
    pages_df = df.dropna(subset=['Date Read', 'Number of Pages']).copy()
    pages_df = pages_df[pages_df['Number of Pages'] != "Unknown"]
    pages_df['Number of Pages'] = pd.to_numeric(pages_df['Number of Pages'], errors='coerce')
    pages_df['YearMonth'] = pd.to_datetime(pages_df['Date Read']).dt.to_period('M')
    pages_per_month = pages_df.groupby('YearMonth')['Number of Pages'].sum()
    return pages_per_month.mean()

@st.cache_data
def calculate_total_pages_read(df):
    """Calculate the total number of pages read."""
    if 'Date Read' not in df.columns or 'Number of Pages' not in df.columns:
        return 0
    pages_df = df.dropna(subset=['Date Read', 'Number of Pages']).copy()
    pages_df = pages_df[pages_df['Number of Pages'] != "Unknown"]
    pages_df['Number of Pages'] = pd.to_numeric(pages_df['Number of Pages'], errors='coerce')
    return pages_df['Number of Pages'].sum()

@st.cache_data
def calculate_most_books_in_one_day(df):
    """Calculate the most books finished in one day."""
    if 'Date Read' not in df.columns:
        return 0
    date_counts = df['Date Read'].dropna().value_counts()
    return date_counts.max() if not date_counts.empty else 0

def display_top_books_by_goodreads_rating(df, top_n):
    """Display the top-rated books by Goodreads averages."""
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
