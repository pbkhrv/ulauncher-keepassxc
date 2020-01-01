EXT_PKG=keepassxc
EXT_DIR=com.github.pbkhrv.ulauncher-keepassxc
EXT_BACKUP_PATH=/tmp/ulauncher-dev-extension-backups

init:
	pip3 install -r scripts/requirements.txt

test:
	pylint main.py ${EXT_PKG}/
	mypy main.py
	eval "PYTHONPATH=`pwd` py.test -v --doctest-modules --flake8 main.py tests/ ${EXT_PKG}/"

run_ul:
	ulauncher --no-extensions --dev -v

run:
	VERBOSE=1 ULAUNCHER_WS_API=ws://127.0.0.1:5054/${EXT_DIR} PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3 `pwd`/main.py

symlink:
	# Backup whatever extension is installed now
	# (if currently installed extension is a symlink, it'll clobber previous backup!)
	mkdir -p ${EXT_BACKUP_PATH}
	rm -rf ${EXT_BACKUP_PATH}/${EXT_DIR}
	cp -r ~/.local/share/ulauncher/extensions/${EXT_DIR} ${EXT_BACKUP_PATH}
	# symlink dev version into ulauncher extensions dir
	rm -rf ~/.local/share/ulauncher/extensions/${EXT_DIR}
	ln -s `pwd` ~/.local/share/ulauncher/extensions/${EXT_DIR}

unlink:
	rm -rf ~/.local/share/ulauncher/extensions/${EXT_DIR}
	cp -r ${EXT_BACKUP_PATH}/${EXT_DIR} ~/.local/share/ulauncher/extensions
