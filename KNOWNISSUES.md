# KNOWN ISSUES

* Exception when providing wrong MFA code
* Credentials are not cached, therefore when using awssso as a credential_process for awscli we make a new STS call for each command and this could be avoided
