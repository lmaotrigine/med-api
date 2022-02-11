[![License](https://img.shields.io/github/license/darthshittious/med-api)](LICENSE)

# A Very Random API

I came up with the idea for this because a prof was boring the shit out of me counting out months on her fingers. I
literally wrote this out on my phone while in class, all the while thinking this is pretty stupid for an API. However, I
would say this is just the beginning, and I'm sure there will be a few additions as I find more things that a computer
is better at doing.

For now, it's up at https://api.varunj.me

## Feature requests

At the end of the day, this is a personal project, and I don't intend to add features on request very often. Unless this
gains traction and users, and a substantial number of people would like to see something implemented, I will not spend
time writing code for it.

That being said, you can go nuts with PRs. Basic knowledge of python and the Flask API are all that is required to
contribute. I'll accept literally anything remotely useful.

## Issues

Issues with existing functionality, or improvements thereof can be suggested, and I'll try to act on it as quick as
possible. Don't open issues to ask questions about usage or functionality. Contact me on Discord or email or maybe in
person.

## Docs?

Too much effort as it stands now. Maybe once I add more features, I'll revisit this. For now, read docstrings.

## Frontend?

Nah. Frontend maintenance would prove to be too much workload for me since I struggle with even the most basic CSS. Feel
free to make your own though.

## Rate limits, Authorisation

| Route | Authorisation Required |
| --- | --- |
| / | No |
| /cat | No |
| /dog | No |
| /gestation | Yes |
| /mean | Yes |
| /median | Yes |
| /mode | Yes |
| /antidepressant-or-tolkien/* | No |
| /patients/* | Yes (not public) |

Authorisation is done using the HTTP `Authorization` header.

For details, visit the `/tokens` endpoint.


## Contributing

Seriously go crazy. I'll accept any good PRs. All I ask is proper docstring and follow PEP8 guidelines.

## Why not get a better domain?

This was free. I'm broke and bad with names, so I named it after myself. Also, it expires in under 6 months. I might not
even move it, who knows. If you don't like it, self-host.
