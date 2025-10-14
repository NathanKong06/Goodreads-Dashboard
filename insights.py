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
        df['Number of Pages'] = df['Number of Pages'].replace(0, pd.NA)
        df['Number of Pages'] = df['Number of Pages'].fillna("Unknown")

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
    handle_missing_pages(df)
    return df

@st.cache_data
def calculate_metrics(df):
    """Calculate key metrics from the data."""
    if 'Exclusive Shelf' in df.columns:
        read_df = df[df['Exclusive Shelf'].str.lower() == 'read']
    else:
        read_df = df.dropna(subset=['Date Read']).copy()

    metrics = {
        "total_books": len(read_df),
        "avg_rating": read_df['My Rating'].mean(),
        "avg_community_rating": read_df['Average Rating'].mean(),
        "total_authors": read_df['Author'].nunique()
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
    fig = px.bar(books_per_year, x='Year', y='Books', text='Books', title="Books Read per Year")
    fig.update_traces(textposition='outside')
    fig.update_xaxes(type='category')
    return fig

@st.cache_data
def generate_top_authors_chart(df, top_n):
    """Generate a bar chart for top authors."""
    if 'Author' not in df.columns or df['Author'].dropna().empty:
        return None, None
    top_authors = df['Author'].value_counts().reset_index()
    top_authors.columns = ['Author', 'Count']
    top_authors = top_authors.head(top_n)
    max_count = top_authors['Count'].max() if not top_authors.empty else 0
    y_max = max(max_count * 1.15, max_count + 1)
    fig = px.bar(
        top_authors,
        x='Author',
        y='Count',
        title=f"Top {top_n} Authors",
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

def calculate_reading_streak(df):
    """Calculate the longest reading streak (consecutive days with books read)."""
    if 'Date Read' not in df.columns or df['Date Read'].isna().all():
        return 0
    dates = pd.to_datetime(df['Date Read'].dropna()).sort_values().unique()
    streak, max_streak = 1, 1
    for i in range(1, len(dates)):
        if dates[i] - dates[i - 1] == timedelta(days=1):
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 1
    return max_streak

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

def calculate_total_pages_read(df):
    """Calculate the total number of pages read."""
    if 'Number of Pages' not in df.columns:
        return 0
    pages_df = df.dropna(subset=['Number of Pages']).copy()
    pages_df = pages_df[pages_df['Number of Pages'] != "Unknown"]
    pages_df['Number of Pages'] = pd.to_numeric(pages_df['Number of Pages'], errors='coerce')
    return pages_df['Number of Pages'].sum()

def calculate_most_books_in_one_day(df):
    """Calculate the most books finished in one day."""
    if 'Date Read' not in df.columns:
        return 0
    date_counts = df['Date Read'].dropna().value_counts()
    return date_counts.max() if not date_counts.empty else 0

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

        # Reading Pace and Pages Insights
        st.subheader("Reading Pace and Pages Insights")
        avg_pages_per_month = calculate_average_pages_per_month(read_df)
        total_pages_read = calculate_total_pages_read(read_df)
        longest_streak = calculate_reading_streak(read_df)
        most_books_in_one_day = calculate_most_books_in_one_day(read_df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Average Pages per Month", f"{avg_pages_per_month:.2f}" if avg_pages_per_month > 0 else "N/A")
        c2.metric("Total Pages Read", f"{int(total_pages_read):,}" if total_pages_read > 0 else "N/A")
        c3.metric("Longest Reading Streak", f"{longest_streak} days" if longest_streak > 0 else "N/A")
        c4.metric("Most Books Completed in One Day", f"{most_books_in_one_day}" if most_books_in_one_day > 0 else "N/A")

        cumulative_pages_chart = generate_cumulative_pages_chart(read_df)
        if cumulative_pages_chart:
            st.plotly_chart(cumulative_pages_chart, use_container_width=True)

        st.subheader("Reading Trends")
        fig1 = generate_books_per_year_chart(read_df)
        if fig1:
            st.plotly_chart(fig1, use_container_width=True)

        st.subheader("Top Authors")
        top_n_authors = st.slider("Select the number of top authors to display:", min_value=5, max_value=30, value=15)
        fig2, top_authors = generate_top_authors_chart(read_df, top_n_authors)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True)
            selected_author = st.selectbox("Select an author to view their books:", top_authors['Author'])
            author_books = (
                read_df[read_df['Author'] == selected_author]
                [['Title', 'My Rating', 'Average Rating', 'Date Read']]
                .sort_values(by='Date Read', ascending=False)
                .reset_index(drop=True)
            )
            format_column(author_books, 'My Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
            format_column(author_books, 'Average Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
            st.write(f"### Books by **{selected_author}** ({len(author_books)} total)")
            st.dataframe(author_books.set_index(pd.Index(range(1, len(author_books) + 1))))
        else:
            st.info("No author data found.")

        top_n_books = st.slider("Select the number of top-rated books to display:", min_value=5, max_value=20, value=10)
        display_top_rated_books(read_df, top_n_books)

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
