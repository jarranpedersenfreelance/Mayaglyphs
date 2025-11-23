# Mayaglyphs Webserver

## Introduction

This is the webserver made for the mayaglyphs.org site 

## Infrastucture

### AWS
This is meant to run on an AWS lightsail instance
The keypair for SSH access to the instance should be stored as PersonalServerKey.pem
After making the lightsail instance, assign it a static IP

### pip3
Make sure pip3 is installed on the server so python3 can import modules
```
sudo yum update -y
sudo yum install python3-pip -y
```

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

        # Headers for proxying
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Increase buffer size
        proxy_buffer_size 128k; 
        proxy_buffers 4 256k; 
        proxy_busy_buffers_size 256k;
    }
}
```
Finally, test the new configuration and restart Nginx
```
sudo nginx -t
sudo systemctl restart nginx
```

### HTTPS
The above steps will allow the server to be accessed at the static IP on port 80 (HTTP)
To enable port 443 (HTTPS) a few more steps are needed
1. Enable port 443 in the IPv4 firewall for the lightsail instance
2. Must have a domain name associated with the instance
3. Install Certbot
```
sudo yum update -y
sudo yum install certbot python3-certbot-nginx -y
```
4. Edit the Nginx config again and change server_name to be the domain instead of the IP (if needed)
```
sudo nano /etc/nginx/nginx.conf
sudo nginx -t
sudo systemctl reload nginx
```
5. Run certbot to generate the https cert
```
sudo certbot --nginx -d domain.com
sudo systemctl reload nginx
```
HTTPS should now be live! Certbot will autorenew the cert every 90 days

## Deployment
Install python modules in .venv
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
Use the deploy.py script to deploy the server both locally (for testing) and remotely
```
./deploy.py local
```
Additionally, use the deploy.py script to deploy the site itself from a zip file separately
```
./deploy.py local-site
```
Note: this will replace the entire contents of ~/site/ on the server (or site/ locally) with the zip file contents
