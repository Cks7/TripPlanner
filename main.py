import streamlit as st
import pandas as pd
from sklearn.metrics.pairwise import haversine_distances, cosine_similarity
from math import radians


# Load the combined dataset
combined_data = pd.read_csv('Final_Prepared_data2.0.csv')

# Sidebar with user input
st.sidebar.header("User Input")

user_budget_level = st.sidebar.slider("Select Budget Level", min_value=1, max_value=5, step=1, value=1)
user_hotel_rating = st.sidebar.slider("Select Hotel Rating", min_value=1, max_value=5, step=1, value=3)
user_hotel_star_rating = st.sidebar.slider("Select Hotel Star Rating", min_value=1, max_value=5, step=1, value=2)
user_restaurant_rating = st.sidebar.slider("Select Restaurant Rating", min_value=1, max_value=5, step=1, value=3)

# Filter based on user criteria
filtered_data = combined_data[
    (combined_data['budget_level'] == user_budget_level) &
    (combined_data['mmt_review_score_Hotel'] >= user_hotel_rating) &
    (combined_data['hotel_star_rating_Hotel'] >= user_hotel_star_rating) &
    (combined_data['Ratings_out_of_5_Restaurant'] >= user_restaurant_rating)
]

# Select the first restaurant based on budget level
selected_restaurant = filtered_data.iloc[0]

# Function to calculate Haversine distance between two coordinates
def calculate_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dist = haversine_distances([[lat1, lon1], [lat2, lon2]]) * 6371000  # Earth radius in meters
    return dist[1, 0]

# Apply the distance calculation to hotels
filtered_data['distance_to_restaurant'] = filtered_data.apply(
    lambda row: calculate_distance(
        selected_restaurant['Latitude_x__Restaurant'],
        selected_restaurant['Longitude_x__Restaurant'],
        row['Latitude_Hotel'],
        row['Longitude_Hotel']
    ),
    axis=1
)

# Rank hotels based on distance and additional criteria
ranked_hotels = filtered_data[filtered_data['Hotel_name'].notnull()].sort_values(
    by=['distance_to_restaurant', 'mmt_review_score_Hotel', 'hotel_star_rating_Hotel']
)

# Select the nearest hotel
nearest_hotel = ranked_hotels.iloc[0]

# Apply the distance calculation to places
filtered_data['distance_to_restaurant'] = filtered_data.apply(
    lambda row: calculate_distance(
        selected_restaurant['Latitude_x__Restaurant'],
        selected_restaurant['Longitude_x__Restaurant'],
        row['Latitude_place_0_x'],
        row['Longitude_place_0_x']
    ),
    axis=1
)

# Rank places based on distance
ranked_places = filtered_data[filtered_data['Name_Place'].notnull()].sort_values(by='distance_to_restaurant')

# Select the nearest place
nearest_place = ranked_places.iloc[0]

# Collaborative Filtering - Content Similarity
hotel_profiles = filtered_data[['mmt_review_score_Hotel', 'hotel_star_rating_Hotel', 'budget_level']]
place_profiles = filtered_data[['Rating_Place', 'Ratings_out_of_5_Restaurant', 'budget_level']]

selected_hotel_profile = selected_restaurant[['mmt_review_score_Hotel', 'hotel_star_rating_Hotel', 'budget_level']]

hotel_similarity = cosine_similarity([selected_hotel_profile], hotel_profiles)
place_similarity = cosine_similarity([selected_hotel_profile], place_profiles)

# Get top 4 hotels and places based on similarity
top_hotels = ranked_hotels.iloc[hotel_similarity.argsort()[0][::-1][:4]]
top_places = ranked_places.iloc[place_similarity.argsort()[0][::-1][:4]]

# Display recommendations in the main area
st.title("Recommendation System App")

st.subheader("Recommendations:")
st.write("-----------------")
st.write(f"Recommended Restaurant: {selected_restaurant['Restaurant_Name']}")
st.write(f"Nearest Hotel: {nearest_hotel['Hotel_name']}")
st.write(f"Nearest Place: {nearest_place['Name_Place']}")
st.write("\nAdditional Information:")
st.write("-----------------------")
st.write(f"Distance to Restaurant: {nearest_hotel['distance_to_restaurant']:.2f} meters")
st.write(f"Hotel Rating: {nearest_hotel['mmt_review_score_Hotel']}")
st.write(f"Hotel Star Rating: {nearest_hotel['hotel_star_rating_Hotel']}")
st.write(f"Restaurant Rating: {selected_restaurant['Ratings_out_of_5_Restaurant']}")

st.write("\nCollaborative Filtering - Top 4 Hotels:")
st.write(top_hotels[['Hotel_name', 'mmt_review_score_Hotel', 'hotel_star_rating_Hotel', 'distance_to_restaurant']])
st.write("\nCollaborative Filtering - Top 4 Places:")
st.write(top_places[['Name_Place', 'Ratings_out_of_5_Restaurant', 'distance_to_restaurant']])
