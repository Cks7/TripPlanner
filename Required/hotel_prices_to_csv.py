import scrapy
import csv

class HotelPriceSpider(scrapy.Spider):
    name = "hotel_price_spider"
    allowed_domains = ["www.makemytrip.com"]
    start_urls = []

    def __init__(self, hotel_names, output_file):
        self.hotel_names = "Hotel Sagar Plaza"
        self.output_file = "hotels_price.csv"

    def start_requests(self):
        with open(self.output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['hotel_name', 'price'])

        for hotel_name in self.hotel_names:
            url = f"https://www.makemytrip.com/hotels/{hotel_name}"
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        hotel_name = response.css(".hotel_name_header span.hotel_name").xpath("text()").get()
        price = response.css(".hotel_price_box .price").xpath("text()").get()

        with open(self.output_file, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([hotel_name, price])

