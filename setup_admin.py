from accounts.models import User
from wallets.models import Wallet

# Create superuser
try:
    admin_user = User.objects.create_superuser(
        username='admin@p2ptrade.com',
        email='admin@p2ptrade.com',
        password='Admin@123456'
    )
    print(f"[OK] Admin user created: {admin_user.email}")
except Exception as e:
    print(f"Admin user already exists or error: {str(e)}")

# Verify users
print(f"Total users in database: {User.objects.count()}")

