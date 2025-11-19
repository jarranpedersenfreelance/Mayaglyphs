# Mayaglyphs Webserver

## Introduction

This is the webserver made for the mayaglyphs.org site 

## Infrastucture

### AWS
This is meant to run on an AWS lightsail instance
The keypair for SSH access to the instance should be stored as PersonalServerKey.pem

### Nginx
In order to serve the webserver on the right port, Nginx is used
To install Nginx on the lightsail instance:
```
sudo yum update -y
sudo yum install nginx -y
```
Then start it and enable it on boot
```
sudo systemctl start nginx
sudo systemctl enable nginx
```
Next open the configuration
```
sudo nano /etc/nginx/nginx.conf
```
Find the location/ block and edit it
```
# Example snippet inside the http or server block of nginx.conf (replace error stubs)
server {
    listen 80;
    server_name LIGHTSAIL_PUBLIC_IP;

    location / {
        # Pass all requests coming to port 80 to the Python server on 1500
        proxy_pass http://127.0.0.1:1500; 

        # Recommended headers for proxying
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Finally, test the new configuration and restart Nginx
```
sudo nginx -t
sudo systemctl restart nginx
```

## Deployment
Use the ./deploy.sh command to deploy the server both locally (for testing) and remotely