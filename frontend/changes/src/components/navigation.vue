<template>
    <div>
        <nav class="navbar navbar-default" style="background-color:#3580ca;">
            <a class="navbar-brand" href="/changes/" style="color:#ffffff;">Change Requests</a>
            <ul class="nav navbar-nav" >
                <li id="changeslink"><a href="/changes/">Changes</a></li>
                <li id="newrequestlink"><a href="/change/request">New Request</a></li>
            </ul>
        </nav>
    </div>
</template>

<script>
export default {
    name: 'Navigation',
}
</script>
<style>
.nav.navbar-nav .active{
    color:
}
.nav.navbar-nav li a {
    color:#ffffff;
}
</style>