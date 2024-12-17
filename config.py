"Api service code configs"
class Config:
    def __init__(self):
        # Rate Limits
        self.rate_limit = 100  # Rate limit per minute for lightweight functions like Login, register
        self.graph_data_rate_limit = 10 # Rate limit per minute for the functions that return graph data
        
        # Database
        self.DATABASE_URL = "mysql+aiomysql://user:pass@1.1.1.1/dbname"
        
        # SMTP Server for e-mail service
        self.smtp_server = "smtpout.secureserver.net"
        self.smtp_port = 0
        self.smtp_username = "mailaddress@mymail.com"
        self.smtp_password = "x"