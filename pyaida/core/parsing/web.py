
import requests
from bs4 import BeautifulSoup

def _get_open_graph_data(url):
    # Send a GET request to fetch the page content
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract Open Graph data from meta tags
        og_data = {}

        # Find and extract 'og:image' tag
        og_image_tag = soup.find('meta', property='og:image')
        og_data['image'] = og_image_tag.get('content') if og_image_tag else None
        
        # Find and extract 'og:title' tag
        og_title_tag = soup.find('meta', property='og:title')
        og_data['title'] = og_title_tag.get('content') if og_title_tag else None
        
        # Find and extract 'og:description' tag
        og_description_tag = soup.find('meta', property='og:description')
        og_data['description'] = og_description_tag.get('content') if og_description_tag else None
        
        return og_data, soup
    else:
        print(f"Failed to fetch page. Status code: {response.status_code}")
        return None


def get_open_graph_data(url:str):
    return _get_open_graph_data(url)[0]
