# Goodreads Reading Insights Dashboard

This project is a Streamlit-based dashboard that provides insights into your Goodreads reading data. By uploading your Goodreads export CSV file, you can visualize and analyze your reading habits, trends, and statistics.

## Features

- **Key Metrics**: View total books read, average ratings, unique authors, and more.
- **Reading Trends**: Analyze books read per year, top authors, and publishers.
- **Pages Insights**: Track cumulative pages read, average pages per month, and total pages read.
- **Top Books**: Discover your top-rated books and books with the highest Goodreads average ratings.
- **Binding and Publication Insights**: Visualize binding distribution and books read by year of publication.
- **Longest and Shortest Books**: Identify the longest and shortest books you've read.
- **Reading Streaks**: Calculate your longest reading streak and most books completed in one day.

## Installation

1. Clone the repository

2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the Streamlit app:

   ```bash
   streamlit run insights.py
   ```

## Usage

1. Export your Goodreads data as a CSV file from the Goodreads website. (<https://help.goodreads.com/s/article/How-do-I-import-or-export-my-books-1553870934590>)
2. Upload the CSV file using the file uploader in the dashboard.
3. Explore the various insights and visualizations provided.

## File Structure

- `insights.py`: Main Streamlit app file containing all the logic for data processing and visualization.
- `requirements.txt`: List of dependencies required to run the app.

## Dependencies

- Python 3.8+
- Streamlit
- Pandas
- Plotly
