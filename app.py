import pandas as pd
from sklearn.metrics.pairwise import haversine_distances, cosine_similarity
from math import radians
import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import folium_static
import hashlib
import sqlite3
from datetime import datetime

# Set page config at the very beginning
st.set_page_config(page_title="Pune Trip Planner", page_icon="🏞️", layout="wide")

# Initialize SQLite databases
user_conn = sqlite3.connect('user_database.db')
user_c = user_conn.cursor()

feedback_conn = sqlite3.connect('feedback_database.db')
feedback_c = feedback_conn.cursor()

# Create tables if they don't exist
user_c.execute('''CREATE TABLE IF NOT EXISTS users
             (username TEXT PRIMARY KEY, password TEXT)''')
user_conn.commit()

feedback_c.execute('''CREATE TABLE IF NOT EXISTS feedback
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT,
              day INTEGER,
              restaurant TEXT,
              restaurant_rating INTEGER,
              hotel TEXT,
              hotel_rating INTEGER,
              place TEXT,
              place_rating INTEGER,
              additional_feedback TEXT,
              timestamp DATETIME)''')
feedback_conn.commit()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    hashed_password = hash_password(password)
    try:
        user_c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        user_conn.commit()
        return True, "Registration successful"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    except Exception as e:
        return False, f"An error occurred: {str(e)}"

def authenticate_user(username, password):
    hashed_password = hash_password(password)
    user_c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    return user_c.fetchone() is not None

def store_feedback(username, day, restaurant, restaurant_rating, hotel, hotel_rating, place, place_rating, additional_feedback):
    feedback_c.execute('''INSERT INTO feedback 
                 (username, day, restaurant, restaurant_rating, hotel, hotel_rating, place, place_rating, additional_feedback, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (username, day, restaurant, restaurant_rating, hotel, hotel_rating, place, place_rating, additional_feedback, datetime.now()))
    feedback_conn.commit()
    return feedback_c.lastrowid

@st.cache_data
def load_data():
    return pd.read_csv('dataset_without_duplicates.csv')

def calculate_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dist = haversine_distances([[lat1, lon1], [lat2, lon2]]) * 6371000  # Earth radius in meters
    return dist[0, 1]

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
    if 0 < budget < 1000:
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

def show_feedback_form(username, day, restaurant, hotel, place):
    with st.expander(f"Feedback for Day {day}", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            restaurant_rating = st.slider(f"Rate {restaurant}", 1, 5, 3, key=f"restaurant_slider_{day}")
            st.write(f"Restaurant: {'⭐' * restaurant_rating}")

        with col2:
            hotel_rating = st.slider(f"Rate {hotel}", 1, 5, 3, key=f"hotel_slider_{day}")
            st.write(f"Hotel: {'⭐' * hotel_rating}")

        with col3:
            place_rating = st.slider(f"Rate {place}", 1, 5, 3, key=f"place_slider_{day}")
            st.write(f"Place: {'⭐' * place_rating}")

        additional_feedback = st.text_area("Any additional feedback?", key=f"additional_feedback_{day}")

        if st.button("Submit Feedback", key=f"submit_feedback_{day}"):
            feedback_id = store_feedback(
                username, day, restaurant, restaurant_rating,
                hotel, hotel_rating, place, place_rating, additional_feedback
            )
            st.success(f"Thank you for your feedback! Feedback ID: {feedback_id}")

def create_map(locations):
    m = folium.Map(location=[18.5204, 73.8567], zoom_start=12)  # Centered on Pune
    for idx, location in locations.iterrows():
        folium.Marker(
            [location['Latitude'], location['Longitude']],
            popup=location['Name'],
            tooltip=location['Type']
        ).add_to(m)
    return m

def get_input_hash(budget, hotel_rating, hotel_star_rating, restaurant_rating, categories):
    input_string = f"{budget}_{hotel_rating}_{hotel_star_rating}_{restaurant_rating}_{'_'.join(sorted(categories))}"
    return hashlib.md5(input_string.encode()).hexdigest()

def auth_page():
    st.title("Pune Trip Planner - Authentication")

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.header("Login")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login"):
                if authenticate_user(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        with tab2:
            st.header("Register")
            new_username = st.text_input("Username", key="register_username")
            new_password = st.text_input("Password", type="password", key="register_password")
            if st.button("Register"):
                if new_username and new_password:
                    success, message = register_user(new_username, new_password)
                    if success:
                        st.success(message)
                        st.info("Please go to the Login tab to sign in.")
                    else:
                        st.error(message)
                else:
                    st.warning("Please enter both username and password.")

    return st.session_state.authenticated

def main():
    # Check authentication
    if not auth_page():
        return

    # Get the username from the session state
    username = st.session_state.get('username', 'Anonymous')

    st.title('🌟 Pune Adventure Planner 🌟')
    st.markdown(f"Welcome, {username}! Discover the best of Pune with our personalized trip recommendations!")

    # Load data
    combined_data = load_data()
    combined_data.drop_duplicates(inplace=True)

    # Sidebar for user preferences
    with st.sidebar:
        st.header('🎛️ Customize Your Adventure')
        user_budget = st.slider('Budget (in dollars)', 0, 5000, 1000, step=100)
        budget_level = get_budget_level(user_budget)

        user_hotel_rating = st.slider('Minimum Hotel Rating', 1, 5, 3)
        user_hotel_star_rating = st.slider('Minimum Hotel Star Rating', 1, 5, 3)
        user_restaurant_rating = st.slider('Minimum Restaurant Rating', 1, 5, 3)
        num_days = st.slider('Number of Days', 1, 7, 3)

        place_categories = [
            'amusement_park_Place', 'art_gallery_Place', 'campground_Place', 'car_rental_Place',
            'cemetery_Place', 'church_Place', 'establishment_Place', 'finance_Place', 'food_Place',
            'gym_Place', 'health_Place', 'hindu_temple_Place', 'lodging_Place', 'museum_Place',
            'park_Place', 'place_of_worship_Place', 'point_of_interest_Place', 'real_estate_agency_Place',
            'shopping_mall_Place', 'store__Place', 'synagogue_Place', 'tourist_attraction_Place',
            'travel_agency_Place', 'zoo_Place'
        ]
        selected_categories = st.multiselect('Select Place Categories', place_categories)

    # Generate input hash
    input_hash = get_input_hash(user_budget, user_hotel_rating, user_hotel_star_rating, user_restaurant_rating, selected_categories)

    # Filter based on user criteria
    filtered_data = combined_data[
        (combined_data['budget_level'] == budget_level) &
        (combined_data['mmt_review_score_Hotel'] >= user_hotel_rating) &
        (combined_data['hotel_star_rating_Hotel'] >= user_hotel_star_rating) &
        (combined_data['Ratings_out_of_5_Restaurant'] >= user_restaurant_rating)
    ]

    if selected_categories:
        filtered_data = filtered_data[filtered_data[selected_categories].any(axis=1)]

    if filtered_data.empty:
        st.error("😕 No suitable recommendations found based on the provided criteria.")
    else:
        for day in range(1, num_days + 1):
            with st.container():
                st.subheader(f"🗓️ Day {day} Itinerary:")

                if 'recommendations' not in st.session_state:
                    st.session_state.recommendations = {}

                if day not in st.session_state.recommendations or st.session_state.recommendations[day].get('input_hash') != input_hash:
                    selected_restaurant = filtered_data.sample(n=1).iloc[0]
                    nearest_hotel, nearest_place, top_hotels, top_places = get_recommendations(filtered_data, selected_restaurant)
                    st.session_state.recommendations[day] = {
                        'input_hash': input_hash,
                        'restaurant': selected_restaurant,
                        'hotel': nearest_hotel,
                        'place': nearest_place,
                        'top_hotels': top_hotels,
                        'top_places': top_places
                    }
                else:
                    selected_restaurant = st.session_state.recommendations[day]['restaurant']
                    nearest_hotel = st.session_state.recommendations[day]['hotel']
                    nearest_place = st.session_state.recommendations[day]['place']
                    top_hotels = st.session_state.recommendations[day]['top_hotels']
                    top_places = st.session_state.recommendations[day]['top_places']

                # Display recommendations
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"🍽️ **Restaurant:** {selected_restaurant['Restaurant_Name']}")
                    st.markdown(f"Rating: {'⭐' * int(selected_restaurant['Ratings_out_of_5_Restaurant'])}")
                with col2:
                    if nearest_hotel is not None:
                        st.markdown(f"🏨 **Hotel:** {nearest_hotel['Hotel_name']}")
                        st.markdown(f"Rating: {'⭐' * int(nearest_hotel['mmt_review_score_Hotel'])}")
                        st.markdown(f"Distance: {nearest_hotel['distance_to_restaurant']:.2f} meters")
                    else:
                        st.markdown("🏨 No suitable hotels found.")
                with col3:
                    if nearest_place is not None:
                        st.markdown(f"🏛️ **Place to Visit:** {nearest_place['Name_Place']}")
                        st.markdown(f"Rating: {'⭐' * int(nearest_place['Rating_Place'])}")
                    else:
                        st.markdown("🏛️ No suitable places found.")
                 # Create a map for the day's locations
                if nearest_hotel is not None and nearest_place is not None:
                    locations = pd.DataFrame({
                        'Name': [selected_restaurant['Restaurant_Name'], nearest_hotel['Hotel_name'], nearest_place['Name_Place']],
                        'Latitude': [selected_restaurant['Latitude_x__Restaurant'], nearest_hotel['Latitude_Hotel'], nearest_place['Latitude_place_0_x']],
                        'Longitude': [selected_restaurant['Longitude_x__Restaurant'], nearest_hotel['Longitude_Hotel'], nearest_place['Longitude_place_0_x']],
                        'Type': ['Restaurant', 'Hotel', 'Place']
                    })
                    st.subheader(f"📍 Day {day} Map")
                    folium_map = create_map(locations)
                    folium_static(folium_map)

                # Show feedback form
                show_feedback_form(
    username,
    day,
    selected_restaurant['Restaurant_Name'],
    nearest_hotel['Hotel_name'] if nearest_hotel is not None else "N/A",
    nearest_place['Name_Place'] if nearest_place is not None else "N/A"
)

        # Additional visualizations
        st.subheader("📊 Trip Overview")
        
        # Budget distribution
        budget_data = pd.DataFrame({
            'Category': ['Hotels', 'Restaurants', 'Activities'],
            'Budget': [user_budget * 0.4, user_budget * 0.3, user_budget * 0.3]
        })
        fig_budget = px.pie(budget_data, values='Budget', names='Category', title='Estimated Budget Distribution')
        st.plotly_chart(fig_budget)

        # Top rated hotels and restaurants
        col1, col2 = st.columns(2)
        with col1:
            top_hotels = filtered_data.nlargest(5, 'mmt_review_score_Hotel')
            fig_hotels = px.bar(top_hotels, x='Hotel_name', y='mmt_review_score_Hotel', title='Top Rated Hotels')
            st.plotly_chart(fig_hotels)
        
        with col2:
            top_restaurants = filtered_data.nlargest(5, 'Ratings_out_of_5_Restaurant')
            fig_restaurants = px.bar(top_restaurants, x='Restaurant_Name', y='Ratings_out_of_5_Restaurant', title='Top Rated Restaurants')
            st.plotly_chart(fig_restaurants)

if __name__ == '__main__':
    main()
