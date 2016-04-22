Summary: WLCG Web Proxy Auto Discovery
Name: wlcg-wpad
Version: 0.1
Release: 1%{?dist}
BuildArch: noarch
Group: Applications/System
License: BSD
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
Source0: https://frontier.cern.ch/dist/%{name}-%{version}.tar.gz

Requires: httpd
Requires: mod_wsgi
Requires: cvmfs-server

%description
Supplies Web Proxy Auto Discovery information for the Worldwide
LHC Computing Grid at URL http://wlcg-wpad.cern.ch/wpad.dat

%prep
%setup -q

%install
mkdir -p $RPM_BUILD_ROOT/etc/wlcg-wpad
install -p -m 644 etc/* $RPM_BUILD_ROOT/etc/wlcg-wpad
mkdir -p $RPM_BUILD_ROOT/etc/cron.d
install -p -m 444 misc/wlcg-wpad.cron $RPM_BUILD_ROOT/etc/cron.d/wlcg-wpad
mkdir -p $RPM_BUILD_ROOT/etc/httpd/conf.d
install -p -m 444 misc/wlcg-wpad.conf $RPM_BUILD_ROOT/etc/httpd/conf.d
mkdir -p $RPM_BUILD_ROOT/var/www/wsgi-scripts
install -p -m 555 misc/wlcg-wpad.wsgi $RPM_BUILD_ROOT/var/www/wsgi-scripts
mkdir -p $RPM_BUILD_ROOT/usr/share/wlcg-wpad/pyweb
install -p -m 444 pyweb/* $RPM_BUILD_ROOT/usr/share/wlcg-wpad/pyweb

%post
/sbin/service httpd status >/dev/null && /sbin/service httpd reload
:

%files
%dir /etc/wlcg-wpad
%config(noreplace) /etc/wlcg-wpad/*
/etc/cron.d/*
/etc/httpd/conf.d/*
/var/www/wsgi-scripts/*
/usr/share/wlcg-wpad

%changelog
* Wed Apr 22 2016 Dave Dykstra <dwd@fnal.gov> - 0.1-1
- Initial version
