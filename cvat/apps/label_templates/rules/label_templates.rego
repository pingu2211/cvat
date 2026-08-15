package labeltemplates

import rego.v1

import data.organizations
import data.utils

# input : {
#     "scope": <"create" | "update" | "delete" | "list" | "view"> or null,
#     "auth": {
#         "user": {
#             "id": <num>,
#             "privilege": <"admin"|"user"|"worker"> or null
#         },
#         "organization": {
#             "id": <num>,
#             "owner": {
#                 "id": <num>
#             },
#             "user": {
#                 "role": <"owner"|"maintainer"|"supervisor"|"worker"> or null
#             }
#         } or null,
#     },
#     "resource": {
#         "id": <num>,
#         "owner": { "id": <num> },
#         "organization": { "id": <num> } or null,
#     }
# }

default allow := false

allow if {
    utils.is_admin
}

# A template of your own, outside of any organization

allow if {
    input.scope == utils.CREATE
    utils.is_sandbox
    utils.has_perm(utils.USER)
}

allow if {
    input.scope in {utils.VIEW, utils.UPDATE, utils.DELETE}
    utils.is_sandbox
    utils.is_resource_owner
}

# Templates of an organization are shared with everyone in it, but only the
# author and the organization staff may change them

allow if {
    input.scope == utils.CREATE
    input.auth.organization.id == input.resource.organization.id
    utils.has_perm(utils.USER)
    organizations.has_perm(organizations.SUPERVISOR)
}

allow if {
    input.scope == utils.VIEW
    input.auth.organization.id == input.resource.organization.id
    organizations.is_member
}

allow if {
    input.scope in {utils.UPDATE, utils.DELETE}
    input.auth.organization.id == input.resource.organization.id
    utils.has_perm(utils.WORKER)
    organizations.has_perm(organizations.SUPERVISOR)
    utils.is_resource_owner
}

allow if {
    input.scope in {utils.UPDATE, utils.DELETE}
    input.auth.organization.id == input.resource.organization.id
    utils.has_perm(utils.WORKER)
    organizations.has_perm(organizations.MAINTAINER)
}

# Listing

allow if {
    input.scope == utils.LIST
    utils.is_sandbox
}

allow if {
    input.scope == utils.LIST
    organizations.is_member
}

base_filter := {} if { # Django Q object to filter list of entries
    utils.is_admin
} else := qobject if {
    utils.is_sandbox
    qobject := {"owner_id": input.auth.user.id}
} else := {} if {
    utils.is_organization
    organizations.is_member
}

filter := utils.add_organization_filter(base_filter, ["organization"])
