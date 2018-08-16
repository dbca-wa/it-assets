
import placeholderImg from './assets/photo_placeholder.svg';

import L from 'leaflet';


var fetchWrap = function (path, base_url, success, failure) {
    fetch(`${base_url}${path}`, {
        credentials: 'include',   
    }).then(function (response) {
        if (!response.ok) {
            throw new Error(`Remote response was a ${response.status}`);
        }
        var contentType = response.headers.get("Content-Type");
        if (!(contentType && contentType.includes("application/json"))) {
            throw new TypeError('Remote response did not have the content type application/json');
        }
        response.json().then(success);
    }).catch(function (error) {
        failure(error);
    });
};

var fetchUsers = function (base_url, success, failure) {
    var formatter = function (raw_data) {
        var data = raw_data.objects.map(function (el) {
            var org_units = el.org_data.units.map(function (fl) {
                return {
                    name: fl.name,
                    acronym: fl.acronym,
                    unit_type: fl.unit_type,
                };
            }).reverse();
            return {
                id: el.pk,
                name: el.name,
                preferred_name: el.preferred_name,
                email: el.email,
                username: el.username,
                title: el.title,
                employee_id: el.employee_id,
                phone_landline: el.telephone,
                phone_extension: el.extension,
                phone_mobile: el.mobile_phone,

                cc_code: el.org_data.cost_centre.code,
                cc_name: el.org_data.cost_centre.name,

                location_id: el.org_unit__location__id,
                location_name: el.org_unit__location__name,
                location_address: el.org_unit__location__address,
                location_pobox: el.org_unit__location__pobox,
                location_phone: el.org_unit__location__phone,
                location_fax: el.org_unit__location__fax,

                photo_url: el.photo_ad ? el.photo_ad : placeholderImg,
                org_units: org_units,
                org_primary: org_units.find(function (fl) {
                    return true;
                }),
                org_secondary: org_units.find(function (fl) {
                    return (fl.unit_type == 'Division (Tier two)') || (fl.unit_type == 'Department (Tier one)');
                }),
                org_search: el.org_data.units.map(function (fl) {
                    return `${fl.name} ${fl.acronym}`;
                }).join(' '),
                visible: true,
            }
        });
        success(data);
    };

    fetchWrap('/api/users/fast/?compact', base_url, formatter, failure);
};


var fetchLocations = function (base_url, success, failure) {
    var formatter = function (raw_data) {
        var data = raw_data.objects.filter(function (el) {
            return el.point && el.active;
        });
        data = data.map(function (el) {
            var pointRegex = /POINT\s*\(([+-]?(?:[0-9]*[.])?[0-9]+)\s+([+-]?(?:[0-9]*[.])?[0-9]+)\)/g;
            var match = pointRegex.exec(el.point);
            return {
                id: el.pk,
                name: el.name,
                email: el.email,
                address: el.address,
                phone: el.phone,
                fax: el.fax,
                coords: L.latLng(match[2], match[1]),
                info_url: el.url,
                bandwidth_url: el.bandwidth_url,
            }
        });
        success(data);
    };

    fetchWrap('/api/locations/', base_url, formatter, failure);
};

var fetchOrg = function (base_url, success, failure) {
    var formatter = function (raw_data) {
        var data = raw_data.objects;
        success(data);
    };
    fetchWrap('/api/options/?list=org_structure', base_url, formatter, failure);
};

export {
    fetchUsers,
    fetchLocations,
    fetchOrg,
}
