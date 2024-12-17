"Database tables metadata"

from sqlalchemy import Table, Column, String, MetaData, DateTime, Integer, Boolean, Double

class Tables:
    def __init__(self):
        self.metadata = MetaData()
        self.APIKEYS = Table(
            "APIKEYS", self.metadata,
            Column("api_key", String(32), primary_key=True),
            Column("telegram_id", String(32), nullable=False),
            Column("creation", DateTime, nullable=False),
            Column("active", Integer, default=1)
        )

        self.WEBSITE = Table(
            "WEBSITE", self.metadata,
            Column("email", String(200), primary_key=True),  # Primary key
            Column("password", String(64)),  # Hashed password
            Column("api_key", String(32)),  # API key
            Column("email_verified", Boolean, default=False),  # Email verification status
            Column("ip_address", String(45)),  # IP address
            Column("session_token", String(64)),  # Session token
            Column("verification_code", String(6)),  # Email verification code
            Column("code_expiry", DateTime),  # Expiry datetime for the verification code
            Column("code_created", DateTime), # Verification key creation time
        )
        
        self.TELEGRAM_AUTH = Table(
            "AUTH", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("telegram_username", String(200)),
            Column("expiry", DateTime),
            Column("telegram_id", Double),
        )
        