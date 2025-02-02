# Generated by Django 5.0.6 on 2024-07-07 06:24

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_app', '0002_cinematography_release_date_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='profile_images')),
                ('first', models.ImageField(default='', upload_to='profile_images')),
                ('second', models.ImageField(default='', upload_to='profile_images')),
                ('third', models.ImageField(default='', upload_to='profile_images')),
                ('forth', models.ImageField(default='', upload_to='profile_images')),
                ('description', models.TextField(default='')),
                ('city', models.TextField(default='')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
