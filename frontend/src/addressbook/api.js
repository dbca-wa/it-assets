
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
        var data = raw_data.map(function (el) {
            return {
                id: el.id,
                name: el.name,
                preferred_name: el.preferred_name,
                email: el.email,
                username: el.username,
                title: el.title,
                phone_landline: el.telephone,
                phone_extension: el.extension,
                phone_mobile: el.mobile_phone,

                parent: el.parent,
                children: el.children,

                location: el.location,

                photo_url: el.photo_ad ? el.photo_ad : `${base_url}${placeholderImg}`,
                org_unit_chain: el.org_unit_chain,
                org_unit: el.org_unit,
                group_unit: el.group_unit,
                org_search: el.org_unit ? `${el.org_unit.name} ${el.org_unit.acronym} ${el.group_unit.name} ${el.group_unit.acronym}` : null,
                location_search: el.location ? el.location.name : null,
                visible: true,
            }
        });
        success(data);
    };

    fetchWrap('/api/v2/departmentuser.json', base_url, formatter, failure);
};


var fetchLocations = function (base_url, success, failure) {
    var formatter = function (raw_data) {
        var data = raw_data.map(function (el) {
            return {
                id: el.id,
                name: el.name,
                email: el.email,
                address: el.address,
                phone: el.phone,
                fax: el.fax,
                coords: el.point ? L.latLng(el.point.coordinates[1], el.point.coordinates[0]) : null,
                info_url: el.url,
                bandwidth_url: el.bandwidth_url,
            }
        });
        success(data);
    };

    fetchWrap('/api/v2/location.json', base_url, formatter, failure);
};

var fetchOrgTree = function (base_url, success, failure) {
    var formatter = function (raw_data) {
        success(raw_data);
    };
    fetchWrap('/api/v2/orgtree.json', base_url, formatter, failure);
};

var fetchOrgUnits = function (base_url, success, failure) {
    var formatter = function (raw_data) {
        var data = raw_data.map(function (el) {
            return {
                id: el.id,
                name: el.name,
                acronym: el.acronym,
                unit_type: el.unit_type,
                manager: el.manager,
                parent: el.parent,
                children: el.children,
                location: el.location,
            }
        });
        success(data);
    };

    fetchWrap('/api/v2/orgunit.json', base_url, formatter, failure);
};


export {
    fetchUsers,
    fetchLocations,
    fetchOrgTree,
    fetchOrgUnits,
}
