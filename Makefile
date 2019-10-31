init:
	pip3 install -r dev/requirements.txt

test:
	pylint keepassxc/
	eval "PYTHONPATH=`pwd` py.test -v --doctest-modules --flake8 tests/ keepassxc/"

run_ul:
	ulauncher --no-extensions --dev -v

run:
	VERBOSE=1 ULAUNCHER_WS_API=ws://127.0.0.1:5054/com.github.pbkhrv.$(ext) PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3 `pwd`/main.py

symlink:
	rm -rf ~/.local/share/ulauncher/extensions/com.github.pbkhrv.$(ext)
	ln -s `pwd` ~/.local/share/ulauncher/extensions/com.github.pbkhrv.$(ext)

unlink:
	rm -rf ~/.local/share/ulauncher/extensions/com.github.pbkhrv.$(ext)
