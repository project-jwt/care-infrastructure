# Setup tutorial illustrations

`SetupTutorial` (`src/components/SetupTutorial.jsx`) shows one illustration per
slide. Files live here and are served from the site root, so a file named
`speak.gif` is referenced as `/tutorial/speak.gif`.

Until a file is added, the slide shows an "Illustration coming soon" placeholder
(the component's `onError` fallback) — nothing breaks.

Expected files (drop GIFs or PNGs/screenshots in with these exact names):

| File           | Slide it illustrates                                  |
| -------------- | ----------------------------------------------------- |
| `speak.gif`    | Speak/record home screen — pressing the big button    |
| `review.gif`   | Reviewing the summary and choosing who to share with  |
| `history.gif`  | History tab — past summaries                           |
| `contacts.gif` | Contacts tab — trusted contacts                        |
| `helpline.gif` | Helpline tab                                           |
| `nav.gif`      | The bottom nav (Speak · History · Contacts · Helpline)|
| `profile.gif`  | Profile button in the header — account management     |

The media slot is a 16:10 box (`object-fit: contain`), so any aspect ratio
displays without cropping; ~640×400 or larger reads well.
