import os
import json
import boto3
import requests
from datetime import datetime
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

class WeatherDashboard:
    def __init__(self):
        self.api_key = os.getenv('OPENWEATHER_API_KEY')
        self.bucket_name = os.getenv('AWS_BUCKET_NAME')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.s3_client = boto3.client(
            's3',
            region_name=self.aws_region,
        )

    def create_bucket_if_not_exists(self):
        """Create S3 bucket if it doesn't exist."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logging.info(f"Bucket '{self.bucket_name}' already exists.")
        except self.s3_client.exceptions.ClientError as e:
            logging.info(f"Bucket '{self.bucket_name}' not found. Creating bucket...")
            try:
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.aws_region},
                )
                logging.info(f"Bucket '{self.bucket_name}' created successfully.")
            except Exception as err:
                logging.error(f"Error creating bucket: {err}")
                raise

    def fetch_weather(self, city, units="imperial"):
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": self.api_key,
            "units": units,
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            logging.info(f"Weather data fetched successfully for '{city}'.")
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching weather data for '{city}': {e}")
            return None

    def save_to_s3(self, weather_data, city):
        """Save weather data to S3 bucket."""
        if not weather_data:
            return False
        
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        file_name = f"weather-data/{city}-{timestamp}.json"
        
        try:
            weather_data['timestamp'] = timestamp
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=json.dumps(weather_data),
                ContentType='application/json'
            )
            logging.info(f"Weather data for '{city}' saved to S3 as '{file_name}'.")
            return True
        except Exception as e:
            logging.error(f"Error saving data to S3 for '{city}': {e}")
            return False

def main():
    dashboard = WeatherDashboard()
    
    dashboard.create_bucket_if_not_exists()
    
    # Dynamic city input
    cities = input("Enter cities separated by commas: ").strip().split(",")
    cities = [city.strip() for city in cities]
    
    # Fetch and save weather data for each city
    for city in cities:
        logging.info(f"Fetching weather data for '{city}'...")
        weather_data = dashboard.fetch_weather(city)
        
        if weather_data:
            temp = weather_data['main']['temp']
            feels_like = weather_data['main']['feels_like']
            humidity = weather_data['main']['humidity']
            description = weather_data['weather'][0]['description']
            
            print(f"\nWeather in {city}:")
            print(f"  Temperature: {temp}°F")
            print(f"  Feels like: {feels_like}°F")
            print(f"  Humidity: {humidity}%")
            print(f"  Conditions: {description}\n")
            
            # Save the data to S3
            dashboard.save_to_s3(weather_data, city)
        else:
            logging.warning(f"Failed to fetch weather data for '{city}'.")


