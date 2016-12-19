## About 
Dataplicity agent is a Python based script which allows remote connection to your device via dataplicity.com. 

It is packaged and delivered using a PEX file for convenience, but you can see the source code here. 

Please feel free to raise issues, fork the code etc. 

## How it works
When you install the Dataplicity Agent on your device, it will opportunistically establish and maintain a secure HTTPS connection to the Dataplicity IoT Router.

When you connect to the Remote Shell via the Dataplicity website, or to the redirected web interface via your device's Wormhole URL, your connection will be routed between your browser and your device via our IoT Router.

In practice, this means that you can access the devices covered by Dataplicity anywhere that they have a viable internet connection. The traffic is routed using encrypted websocket connections, and is robust enough to be used in instances where the internet coverage is flaky. Because the device itself is the originator of the connection, traditional impediments to remote access (such as NAT, firewalls and dynamic IP addressing) are no longer an issue.

For more information, see https://docs.dataplicity.com

## License 
Dataplicity agent is licensed under a modified-BSD license. If you have any thoughts on different types of licensing, please raise an issue.
