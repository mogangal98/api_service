This code is a FastAPI service that provides some crypto exchange data to users. 
The data is a custom, processed version of information gathered from several 
crypto exchange sites (like Binance). People can access this data by registering 
and verifying their email on our website, and by using an API key they get from our Telegram bot. 
Only those who have bought our Telegram app (and have an active API key) can use this service.
The service is designed to be accessed by three different components:
1.(Under Development) Windows desktop application
2.(Under Development) Website
3.Directly as an API service (for external integrations)

This code is a simplified baseline version of our original API service,
intended for demonstration purposes on GitHub. Sensitive information and 
certain implementation details have been removed or modified. 
API service handles user registration, email verification, 
API key management, and data retrieval. The API key is what gives access, 
ensuring only paid users from our Telegram app (and subsequently our planned Windows app and website) can fetch the processed crypto data.