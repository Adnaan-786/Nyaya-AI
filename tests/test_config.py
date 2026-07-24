from app.config import get_settings

settings = get_settings()

print(settings.app_name)
print(settings.environment)
print(settings.database_url)
print(settings.fake_mode)