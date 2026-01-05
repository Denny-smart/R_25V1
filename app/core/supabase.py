from supabase import create_client, Client
from app.core.settings import settings

# Initialize Supabase client
# We use the Service Role Key for backend administration (checking profiles, approving users)
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
