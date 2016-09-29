Summary: WLCG Web Proxy Auto Discovery
Name: wlcg-wpad
Version: 0.6
Release: 1%{?dist}
BuildArch: noarch
Group: Applications/System
License: BSD
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
Source0: https://frontier.cern.ch/dist/%{name}-%{version}.tar.gz

Requires: httpd
Requires: mod_wsgi
Requires: cvmfs-server
Requires: python-anyjson
Requires: python-netaddr

%description
Supplies Web Proxy Auto Discovery information for the Worldwide
LHC Computing Grid at URL http://wlcg-wpad.cern.ch/wpad.dat

%prep
%setup -q

%install
mkdir -p $RPM_BUILD_ROOT/etc/cron.d
install -p -m 444 misc/wlcg-wpad.cron $RPM_BUILD_ROOT/etc/cron.d/wlcg-wpad
mkdir -p $RPM_BUILD_ROOT/etc/httpd/conf.d
install -p -m 444 misc/wlcg-wpad.conf $RPM_BUILD_ROOT/etc/httpd/conf.d/10-wlcg-wpad.conf
mkdir -p $RPM_BUILD_ROOT/var/www/wsgi-scripts
install -p -m 555 misc/wlcg-wpad.wsgi $RPM_BUILD_ROOT/var/www/wsgi-scripts
mkdir -p $RPM_BUILD_ROOT/usr/share/wlcg-wpad/pyweb
install -p -m 555 misc/sync_wpad_conf $RPM_BUILD_ROOT/usr/share/wlcg-wpad
mkdir -p $RPM_BUILD_ROOT/usr/share/wlcg-wpad/pyweb
install -p -m 444 pyweb/* $RPM_BUILD_ROOT/usr/share/wlcg-wpad/pyweb
mkdir -p $RPM_BUILD_ROOT/var/lib/wlcg-wpad

%post
cvmfs_server update-geodb
/usr/share/wlcg-wpad/sync_wpad_conf
/sbin/service httpd status >/dev/null && /sbin/service httpd reload
:

%postun
if [ $1 = 0 ]; then
    rm -rf /var/lib/wlcg-wpad
fi

%files
/etc/cron.d/*
/etc/httpd/conf.d/*
/var/www/wsgi-scripts/*
/usr/share/wlcg-wpad
/var/lib/wlcg-wpad


%changelog
* Tue Sep 20 2016 Dave Dykstra <dwd@fnal.gov> - 0.6-1
- Return specific error messages from wlcg_wpad module to the user
  rather than a generic "No proxy found"

* Tue Sep 20 2016 Dave Dykstra <dwd@fnal.gov> - 0.5-1
- Add support for client load balancing of proxies
- If "cmsnames" is present in the data, add those to the first line comment
  in the form "; CMS: sitename,..."

* Wed Aug 03 2016 Dave Dykstra <dwd@fnal.gov> - 0.4-1
- Disable the entries that are marked "disabled"
- When there's a match, print "// For sitename, ..." as a leading comment

* Wed Aug 03 2016 Dave Dykstra <dwd@fnal.gov> - 0.3-1
- Convert to reading from worker-proxies.json instead of grid-squids.json

* Fri Jun 03 2016 Dave Dykstra <dwd@fnal.gov> - 0.2-1
- Add initial implementation of wlcg-wpad.cern.ch
- Copy config files from wlcg-squid-monitor.cern.ch
- Rename apache config to 10-wlcg-wpad.conf to give it order priority

* Wed Apr 22 2016 Dave Dykstra <dwd@fnal.gov> - 0.1-1
- Initial version
