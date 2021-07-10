# Spideriment
**Spideriment** *(spider + experiment)* is a **web crawler** (web spider, indexer) written in Python. 
Originally, it was just a personal experiment, but since the program was able to run for several weeks without any issues, I decided to publish it.



## Features and characteristics
* The crawler is **multi-threaded**.
* It's designed to route all of its internet traffic through a local **Tor** SOCKS proxy which prevents your IP address from getting on abuse lists.
* It respects disallowed and allowed URLs in **robots.txt** files (and "robots" meta tags), but **not other things, such as crawl delays**. 
  * *(This would be difficult to incorporate into the crawler's design and due to the program's experimental nature, I decided not to implement it.)*
  * The program has an internal in-memory robots.txt cache to speed up crawling and to lower network traffic.
* It has a configurable **URL filter** (hostname and path filter), **language allow list** and **mobile pages filter**.
* The web index is saved to a CSV file whose format is specified in [web_index_spec.txt](web_index_spec.txt).



## DISCLAIMER
**Using Tor or web crawlers may be illegal in some countries. 
The web crawler may navigate to websites that are illegal in your country, and there is no way to prevent this behavior!**

**Use the program with caution and within the law!
The author is not liable for any damage and legal issues caused by this program and its usage!**



## Usage

### 1. Requirements
   * **Linux**
   * **Python 3.7+**
   
   The program was tested in Python 3.7 (Debian 10) and Python 3.8 (Ubuntu 20.04).
 

### 2. Install the dependencies
   On Debian/Ubuntu and their derivatives, execute the following:
   ```
   sudo apt update 
   sudo apt install python3 python3-pip python3-venv python3-virtualenv virtualenv
   ```


### 3. Change the configuration to fit your needs
  The crawler's configuration can be changed in the **[Settings.py](src/Settings.py)** file.


### 4. Run, monitor and stop the program
  The bash script [run_spideriment.sh](src/run_spideriment.sh) prepares the environment and then **runs the program**:

  ```
  ./run_spideriment.sh
  ```

  To **monitor what the crawler is doing**, you can connect to its logger socket (e.g. using netcat or telnet) whose IP address and port is set in the [Settings.py](src/Settings.py) file.

  To **stop the crawler**, send a ``SIGTERM``, ``SIGINT`` or ``SIGHUP`` signal to the program, e.g. by pressing Ctrl+C at the terminal where the crawler is running.
  The crawler will finish its current batch (which can take really long – be patient!) and safely exit.

  You can also install a [systemd service](src/spideriment.service) to be able to run the crawler automatically on startup (on Linux distributions that use systemd).



## Related projects
* **[Spideriment Search Server](https://github.com/vitlabuda/spideriment_search_server)** – search server for use by frontends
* **[Spideriment Web Search](https://github.com/vitlabuda/spideriment_web_search)** – web frontend (search engine)



## Licensing
This project is licensed under the 3-clause BSD license. See the [LICENSE](LICENSE) file for details.

Written by [Vít Labuda](https://vitlabuda.cz/).
