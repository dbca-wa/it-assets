
export default function (base_url, success, failure) {
    fetch(`${base_url}/api/users/fast/?compact`, {
        credentials: 'include',   
    }).then(function (response) {
        if (!response.ok) {
            throw new Error(`Remote response was a ${response.status}`);
        }
        var contentType = response.headers.get("Content-Type");
        if (!(contentType && contentType.includes("application/json"))) {
            throw new TypeError('Remote response did not have the content type application/json');
        }
        response.json().then(function (raw_data) {
            var data = raw_data.objects.map(function (el) {
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

                    photo_url: el.photo_ad,
                    org_units: el.org_data.units.map(function (fl) {
                        return {
                            name: fl.name,
                            acronym: fl.acronym,
                        };
                    }),
                    org_search: el.org_data.units.map(function (fl) {
                        return `${fl.name} ${fl.acronym}`;
                    }).join(' '),
                    visible: true,
                }
            });
            success(data);
        });
    }).catch(function (error) {
        failure(error);
    });
}
