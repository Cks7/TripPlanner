import pandas as pd
from sklearn.metrics.pairwise import haversine_distances, cosine_similarity
from math import radians
import streamlit as st

# Load the combined dataset
combined_data = pd.read_csv('Final_Prepared_data2.0.csv')

# Remove duplicate entries
combined_data.drop_duplicates(inplace=True)

def calculate_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dist = haversine_distances([[lat1, lon1], [lat2, lon2]]) * 6371000  # Earth radius in meters
    return dist[1, 0]

def get_recommendations(filtered_data, selected_restaurant):
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

    # Select the nearest hotel if there are any
    nearest_hotel = ranked_hotels.iloc[0] if not ranked_hotels.empty else None

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

    # Select the nearest place if there are any
    nearest_place = ranked_places.iloc[0] if not ranked_places.empty else None

    # Collaborative Filtering - Content Similarity
    hotel_profiles = filtered_data[['mmt_review_score_Hotel', 'hotel_star_rating_Hotel', 'budget_level']]
    place_profiles = filtered_data[['Rating_Place', 'Ratings_out_of_5_Restaurant', 'budget_level']]

    selected_hotel_profile = selected_restaurant[['mmt_review_score_Hotel', 'hotel_star_rating_Hotel', 'budget_level']]

    hotel_similarity = cosine_similarity([selected_hotel_profile], hotel_profiles)
    place_similarity = cosine_similarity([selected_hotel_profile], place_profiles)

    # Get top 4 hotels and places based on similarity
    top_hotels = ranked_hotels.iloc[hotel_similarity.argsort()[0][::-1][:4]]
    top_places = ranked_places.iloc[place_similarity.argsort()[0][::-1][:4]]

    return nearest_hotel, nearest_place, top_hotels, top_places

def get_budget_level(budget):
    if 0<budget<1000:
        return 0
    if budget <= 1000:
        return 1
    elif 1000 < budget <= 2000:
        return 2
    elif 2000 < budget <= 3000:
        return 3
    elif 3000 < budget <= 4000:
        return 4
    else:
        return 5

def main():
    st.title('Trip Planner For Pune')

    st.sidebar.header('User Preferences')
    user_budget = st.sidebar.number_input('Budget (in dollars)', min_value=0, step=100, value=1000)

    # Map budget to budget level
    budget_level = get_budget_level(user_budget)

    st.sidebar.write('Budget Level:')
    st.sidebar.write('0-1000: Budget Level 1')
    st.sidebar.write('1000-2000: Budget Level 2')
    st.sidebar.write('2000-3000: Budget Level 3')
    st.sidebar.write('3000-4000: Budget Level 4')
    st.sidebar.write('4000+: Budget Level 5')

    user_hotel_rating = st.sidebar.number_input('Hotel Rating', min_value=1, step=1, value=1)
    user_hotel_star_rating = st.sidebar.number_input('Hotel Star Rating', min_value=1, step=1, value=1)
    user_restaurant_rating = st.sidebar.number_input('Restaurant Rating', min_value=1, step=1, value=1)
    num_days = st.sidebar.number_input('Number of Days', min_value=1, step=1, value=3)

    # Filter based on user criteria, including the new budget level
    filtered_data = combined_data[
        (combined_data['budget_level'] == budget_level) &
        (combined_data['mmt_review_score_Hotel'] >= user_hotel_rating) &
        (combined_data['hotel_star_rating_Hotel'] == user_hotel_star_rating) &
        (combined_data['Ratings_out_of_5_Restaurant'] >= user_restaurant_rating)
    ]

    # Check if the filtered dataset is empty
    if filtered_data.empty:
        st.error("No suitable recommendations found based on the provided criteria.")
    else:
        # Loop through the specified number of days to provide recommendations
        for day in range(1, num_days + 1):
            st.subheader(f"Recommendations for Day {day}:")

            # Select the restaurant for the day (you might have a different logic to select it)
            selected_restaurant = filtered_data.sample(n=1).iloc[0]

            # Get recommendations for the selected restaurant
            nearest_hotel, nearest_place, top_hotels, top_places = get_recommendations(filtered_data, selected_restaurant)

            # Display the recommendations
            st.write(f"Recommended Restaurant: {selected_restaurant['Restaurant_Name']}")
            if nearest_hotel is not None:
                st.write(f"Nearest Hotel: {nearest_hotel['Hotel_name']}")
            else:
                st.write("No hotels found meeting the criteria.")

            if nearest_place is not None:
                st.write(f"Nearest Place: {nearest_place['Name_Place']}")
            else:
                st.write("No places found meeting the criteria.")

            st.write("\nAdditional Information:")
            if nearest_hotel is not None:
                st.write(f"Distance to Nearest Hotel: {nearest_hotel['distance_to_restaurant']:.2f} meters")
                st.write(f"Hotel Rating: {nearest_hotel['mmt_review_score_Hotel']}")
                st.write(f"Hotel Star Rating: {nearest_hotel['hotel_star_rating_Hotel']}")
            else:
                st.write("No hotels found meeting the criteria.")

            st.write(f"Restaurant Rating: {selected_restaurant['Ratings_out_of_5_Restaurant']}")

            st.write("\nCollaborative Filtering - Top 4 Hotels:")
            st.write(top_hotels[['Hotel_name', 'mmt_review_score_Hotel', 'hotel_star_rating_Hotel', 'distance_to_restaurant']])

            st.write("\nCollaborative Filtering - Top 4 Places:")
            st.write(top_places[['Name_Place', 'Ratings_out_of_5_Restaurant', 'distance_to_restaurant']])

            # Google Maps embed code for nearest hotel
            if nearest_hotel is not None:
                st.write(f"\nLocation of Nearest Hotel ({nearest_hotel['Hotel_name']}):")
                html = f"""
                <iframe 
                    width="300" 
                    height="300" 
                    frameborder="0" 
                    scrolling="no" 
                    marginheight="0" 
                    marginwidth="0" 
                    src="https://www.google.com/maps/embed/v1/place?q={nearest_hotel['Latitude_Hotel']},{nearest_hotel['Longitude_Hotel']}&key=AIzaSyC7lBNwG15UuS57EIqxG3b1guKJgPwNU7g">
                </iframe>
                """
                st.components.v1.html(html, width=300, height=300)

if __name__ == '__main__':
    main()
