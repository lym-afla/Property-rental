from django.test import TestCase

# Making django app work
# import os
# import django
# import sys

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commerce.settings')
# print(os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commerce.settings'))

# from django.core.management import execute_from_command_line
# execute_from_command_line(sys.argv)

# django.setup()

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commerce.settings')


from models import Listing

# Create your tests here.
print(Listing.get(0))
