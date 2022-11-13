FormShare Analytics Plug-in
==============

This plug-in provides core functions for **decentralized** analytics. Most notably SQL sand-boxing. 

Getting Started
---------------

- Activate the FormShare environment.
```
$ . ./path/to/FormShare/bin/activate
```

- Change directory into your newly created plugin.
```
$ cd analytics
```

- Build the plugin
```
$ python setup.py develop
```

- Add the plugin to the FormShare list of plugins by editing the following line in development.ini or production.ini
```
    #formshare.plugins = examplePlugin
    formshare.plugins = analytics
```

- Run FormShare again
