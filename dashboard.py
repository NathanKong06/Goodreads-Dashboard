import insights_functions
import enrich
import pandas as pd
import streamlit as st
import os

def main():
    st.set_page_config(page_title="Goodreads Dashboard",page_icon="📚",layout="wide")
    st.title("Goodreads Reading Insights Dashboard")

    st.markdown(
        """
    ### How to get your Goodreads CSV
    1. Visit **Goodreads Import/Export**: https://www.goodreads.com/review/import and select "Export Library" to download your reading data.
    - Follow the official instructions to export your library as a CSV if needed:  
       https://help.goodreads.com/s/article/How-do-I-import-or-export-my-books-1553870934590
    """
    )

    uploaded_file = st.file_uploader("Upload your Goodreads export CSV", type=["csv"])

    if uploaded_file is not None:
        if 'uploaded_file_name' not in st.session_state:
            st.session_state.uploaded_file_name = getattr(uploaded_file, "name", "goodreads_export.csv")
    
    if uploaded_file is not None:
        df = insights_functions.preprocess_data(uploaded_file)
        if df is None:
            return  
        read_df, metrics = insights_functions.calculate_metrics(df)
        insights_functions.display_metrics(metrics)

        tab_titles = ["Reading Pace", "Trends & Authors", "Publishers & Binding", "Top Books", "Longest & Shortest Books", "Enrich Data with Genres", "Raw Data"]
        
        selected_tab = st.radio(
            "Select a section:",
            tab_titles,
            key='active_tab', 
            horizontal=True
        )
        st.markdown("---") 
        
        if selected_tab == "Reading Pace":
            st.subheader("Reading Pace and Pages Insights")
            avg_pages_per_month = insights_functions.calculate_average_pages_per_month(read_df)
            total_pages_read = insights_functions.calculate_total_pages_read(read_df)
            longest_streak, streak_start, streak_end = insights_functions.calculate_reading_streak(read_df)
            avg_pages_per_book = insights_functions.calculate_average_pages_per_book(read_df)
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
            c4.metric("Average Pages per Book", f"{avg_pages_per_book:.2f}" if avg_pages_per_book > 0 else "N/A")

            cumulative_pages_chart = insights_functions.generate_cumulative_pages_chart(read_df)
            if cumulative_pages_chart:
                st.plotly_chart(cumulative_pages_chart, width='stretch')

        elif selected_tab == "Trends & Authors":
            st.subheader("Reading Trends")
            fig1 = insights_functions.generate_books_per_year_chart(read_df)
            if fig1:
                st.plotly_chart(fig1, width='stretch')

            st.subheader("Top Authors")
            top_n_authors = st.slider("Select the number of top authors to display:", min_value=5, max_value=20, value=10, key="top_authors_slider")
            fig2, top_authors = insights_functions.generate_top_authors_chart(read_df, top_n_authors)
            if fig2:
                st.plotly_chart(fig2, width='stretch')
                selected_author = st.selectbox("Select an author to view their books:", top_authors['Author'], key="author_selectbox")
                author_books = insights_functions.get_books_by_author(read_df, selected_author)
                author_books = author_books[['Title', 'Author', 'My Rating', 'Average Rating', 'Date Read']].sort_values(by='Date Read', ascending=False).reset_index(drop=True)
                insights_functions.format_column(author_books, 'My Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
                insights_functions.format_column(author_books, 'Average Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
                st.write(f"### Books by **{selected_author}** ({len(author_books)} total)")
                st.table(author_books.set_index(pd.Index(range(1, len(author_books) + 1))))
            else:
                st.info("No author data found.")

        elif selected_tab == "Publishers & Binding":
            st.subheader("Publisher Insights")
            top_n_publishers = st.slider("Select the number of top publishers to display:", min_value=3, max_value=10, value=5, key="top_publishers_slider")
            top_publishers_chart = insights_functions.generate_top_publishers_chart(read_df, top_n_publishers)
            if top_publishers_chart:
                st.plotly_chart(top_publishers_chart, width='stretch')

            st.subheader("Binding Distribution")
            binding_distribution_chart = insights_functions.generate_binding_distribution_chart(read_df)
            if binding_distribution_chart:
                st.plotly_chart(binding_distribution_chart, width='stretch')

            st.subheader("Books Read by Year Published")
            books_by_year_published_chart = insights_functions.generate_books_by_year_published_chart(read_df)
            if books_by_year_published_chart:
                st.plotly_chart(books_by_year_published_chart, width='stretch')

            if 'Year Published' in read_df.columns:
                available_years = sorted(read_df['Year Published'].dropna().unique())
                selected_pub_year = st.selectbox("Select a publication year to view books from that year:", available_years, key="pub_year_selectbox")

                books_in_year = read_df[read_df['Year Published'] == selected_pub_year].copy()
                books_in_year = books_in_year[['Title', 'Author', 'My Rating', 'Average Rating', 'Date Read']].sort_values(by='Date Read', ascending=False).reset_index(drop=True)

                insights_functions.format_column(books_in_year, 'My Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
                insights_functions.format_column(books_in_year, 'Average Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")

                st.write(f"### Books Published in {selected_pub_year} ({len(books_in_year)} total)")
                st.table(books_in_year.set_index(pd.Index(range(1, len(books_in_year) + 1))))
            else:
                st.info("No publication year data found.")

        elif selected_tab == "Top Books":
            st.subheader("Your Top Rated Books")
            top_n_books = st.slider("Select the number of top-rated books to display:", min_value=5, max_value=20, value=10, key="top_rated_books_slider")
            insights_functions.display_top_rated_books(read_df, top_n_books)

            st.subheader("Top Books by Goodreads Average Rating")
            top_n_goodreads_books = st.slider("Select the number of top Goodreads-rated books to display:", min_value=5, max_value=20, value=10, key="goodreads_top_books_slider")
            insights_functions.display_top_books_by_goodreads_rating(read_df, top_n_goodreads_books)

        elif selected_tab == "Longest & Shortest Books":
            insights_functions.display_longest_shortest_books(read_df)

        elif selected_tab == "Enrich Data with Genres":
            st.subheader("Enrich Your Data with Genres")
            st.write("Would you like to enrich your reading data with genre information from Goodreads? This will fetch genre data for each book in your library.")
            
            if st.button("Enrich Library with Genres", key="enrich_button"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                status_text.text("Preparing to fetch genre data...")

                def _progress_callback(done: int, total: int):
                    try:
                        if total and total > 0:
                            pct = int((done / total) * 100)
                        else:
                            pct = 100 if done >= total else 0
                    except Exception:
                        pct = 0
                    try:
                        progress_bar.progress(min(max(pct, 0), 100))
                        if total and total > 0:
                            status_text.text(f"Fetching genre data... ({done}/{total})")
                        else:
                            status_text.text("No books to enrich.")
                    except Exception:
                        pass

                enriched_df = enrich.enrich_library(read_df, progress_callback=_progress_callback)

                progress_bar.progress(100)
                status_text.text("Enrichment complete!")
                
                if enriched_df is not None:
                    if 'Genres' in enriched_df.columns:
                        enriched_df['Genres'] = enriched_df['Genres'].apply(
                            lambda x: ' | '.join(x) if isinstance(x, list) else x
                        )
                    
                    st.session_state.enriched_df = enriched_df
                    st.session_state.enrichment_complete = True
                    st.success("Your data has been enriched with genres!")
                else:
                    st.error("An error occurred while enriching the data.")
            
            has_genres_in_read = ('Genres' in read_df.columns) and (not read_df['Genres'].isna().all())
            enriched_present = 'enriched_df' in st.session_state

            if has_genres_in_read or enriched_present:
                df_for_genres = st.session_state.enriched_df if enriched_present else read_df

                st.subheader("Genre Insights")
                st.write("Explore genre distribution across your library.")

                try:
                    csv_bytes = df_for_genres.to_csv(index=False).encode('utf-8')
                    if enriched_present:
                        download_name = f"enriched_{st.session_state.get('uploaded_file_name', 'goodreads_export.csv')}"
                    else:
                        download_name = f"with_genres_{st.session_state.get('uploaded_file_name', 'goodreads_export.csv')}"
                    st.download_button("Download Enriched CSV", data=csv_bytes, file_name=download_name, mime="text/csv")
                except Exception as e:
                    st.error(f"Unable to prepare download: {e}")

                st.write("If you are running Streamlit locally and want to save the CSV directly to a path on this machine, specify the path below.")
                save_locally = st.checkbox("Save CSV to local path", key="save_local_checkbox")
                if save_locally:
                    default_name = st.session_state.get('uploaded_file_name', 'goodreads_export.csv')
                    default_path = os.path.join(os.getcwd(), default_name)
                    save_path = st.text_input("Full path to save CSV (will overwrite if exists):", value=default_path, key="save_path_input")
                    if st.button("Save CSV to Path", key="save_path_button"):
                        try:
                            df_for_genres.to_csv(save_path, index=False)
                            st.success(f"CSV saved to: {save_path}")
                        except Exception as e:
                            st.error(f"Failed to save CSV to {save_path}: {e}")
                
                if 'Genres' in df_for_genres.columns:
                    top_n_genres = st.slider("Select the number of top genres to display:", min_value=5, max_value=20, value=10, key="top_genres_slider", label_visibility="collapsed")
                    genre_chart = insights_functions.generate_top_genres_chart(df_for_genres, top_n_genres)
                    if genre_chart:
                        st.plotly_chart(genre_chart, width='stretch')
                    else:
                        st.info("No genre data available to plot.")
                else:
                    st.info("No genre data available yet.")
            else:
                st.info("No genre data available. Click 'Enrich Library with Genres' to fetch genres from Goodreads.")

        elif selected_tab == "Raw Data":
            if 'enriched_df' in st.session_state:
                display_df = st.session_state.enriched_df.copy()
            else:
                display_df = read_df.copy()
            
            insights_functions.format_column(display_df, 'My Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
            insights_functions.format_column(display_df, 'Average Rating', lambda x: f"{x:.2f}" if pd.notna(x) else "")
            st.dataframe(display_df.set_index(pd.Index(range(1, len(display_df) + 1))))
    else:
        st.info("Upload your Goodreads CSV file to see your reading insights.")

if __name__ == "__main__":
    main()