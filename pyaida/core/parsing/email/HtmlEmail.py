import base64
import email
from email import policy
from email.parser import BytesParser
from bs4 import BeautifulSoup
import typing
from pyaida.core.data import AbstractEntityModel
from pydantic import BaseModel, model_validator
from pyaida.core.utils import sha_hash
import html2text
        
class HtmlEmail(AbstractEntityModel):
    """You are an email and newsletter agent. If asked about emails or newsletters you can run a search to answer the users question.
    
    """
    class Config:
        namespace: str = "public"
        functions: dict = {"test":"desc"}
        
    content: typing.Optional[str] = None
    sender: str 
    receiver: str
    subject:str
    date: str
    
    @model_validator(mode="before")
    def _val(cls, values):
        """validation for default vals.
           ids is easy to generate from required fields.
           description should be markdown of the html
        """
        if not values.get('description') and values.get('content'):
            try:
                values['description'] = html2text.html2text(values['content'])
            except:
                values['description'] = values.get('content')
        """set the id if its not set"""
        if not values.get('id') and values.get('sender') and values.get('date'):
            values['id'] = sha_hash({
                'sender': values['sender'],
                'date':values['date']
            })
            
        return values
    
    
    def _repr_html_(self):
        return self.content
    
    def to_markdown(self):
        """convert the html content to markdown"""

        markdown = html2text.html2text(self.content)
        return markdown
    
 

    @classmethod
    def parse_raw_to_html(cls, raw_email):
        """parse an email from raw bytes tested on gmail"""
        
        raw_email_bytes = base64.urlsafe_b64decode(raw_email)
        msg = BytesParser(policy=policy.default).parsebytes(raw_email_bytes)
        html = None

        email_metadata = {
            "sender": msg["From"],
            "receiver": msg["To"],
            "subject": msg["Subject"],
            "date": msg["Date"],
        }

        html_content = None
        markdown = None
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content = part.get_payload(decode=True).decode(part.get_content_charset())
                    break
        else:
            if msg.get_content_type() == "text/html":
                html_content = msg.get_payload(decode=True).decode(msg.get_content_charset())

        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            html = soup.prettify()
            markdown = html2text.html2text(html)
            
        id = sha_hash({
            'sender': email_metadata["sender"],
            'date': email_metadata["date"]
        })

        return HtmlEmail(**email_metadata, content=html,description=markdown, id=id)

 