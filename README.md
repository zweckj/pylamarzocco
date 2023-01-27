# La Marzocco Cloud
This is a library to interface with La Marzocco's cloud.

It's in experimentals stages and meant mainly to connect to the Micra, as for the other IoT enabled machines you can use the [lmdirect](https://github.com/rccoleman/lmdirect) library.

# Libraries in this project
- `lmlocalapi` calls the new local API the Micra exposes, using the Bearer token from the customer cloud endpoint. However, this API currently only supports getting the config and not setting anything (to my knowledge). If La Marzocco updates the firmware or more endpoints are found this library will be updated to reflect those additional endpoints.
- `lmcloud` interacts with `gw.lamarzocco.com` to send commands. lmcloud can be initialized to only issue remote commands, or to initialize an instance of `lmlocalapi` for getting the current machine settings. This helps to avoid flooding the cloud API and is faster overall.
