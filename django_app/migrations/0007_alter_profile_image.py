# Generated by Django 5.0.6 on 2024-07-11 14:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_app', '0006_alter_profile_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='image',
            field=models.ImageField(default='profile_images/Cool-avatars-anonymous-avatar.jpg', upload_to='profile_images'),
        ),
    ]
