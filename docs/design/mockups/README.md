# Mockups

If a screen changes, update the matching HTML file in the same change.

Each file is one screen. The order of this list is the flow. Links inside each screen point at these same files.

## Access

1. [Login](access/login.html). Sign in with Google, email, or a demo account (client or pharmacy).
2. [Sign up with Google](access/sign-up.html). Choose a role (client or pharmacy), link Google, and fill in the details.

## Client

1. [Request a quote](client/01-request-quote.html). Enter the preparation: type, formula, presentation, and urgency.
2. [Choose pharmacies](client/02-choose-pharmacies.html). Pick pharmacies and labs on the map, filtered by distance and minimum score. The search area is shown and cannot be edited. Each result shows its score, or “Sin reseñas aún”. The review carousel sits outside the selectable card, on a transparent background and at the same width. Each card shows its date, and the newest review is the first one. The scrollbar stays hidden: drag with the mouse or use the side arrows. Map badges keep the pharmacy name and add the score beside it. A map control recenters on the chosen location at the 1 km zoom and leaves the selected radius unchanged.
3. [My orders](client/03-my-orders.html). Orders by status: waiting for quotes, quoted, in progress, and finished.
4. [Pharmacy chat](client/04-pharmacy-chat.html). Compare quotes for one order and continue the chat with each pharmacy. After the order is delivered, the right column lets the client leave a 1–5 score and an optional short comment. A saved review shows its date.
5. [Profile](client/05-profile.html). Personal details, location, and notification preferences.

## Mail

1. [New request](mail/new-request.html). Email a pharmacy receives when a client asks for a quote.

## Pharmacy

1. [Pending quotes](pharmacy/01-pending-quotes.html). Requests with no reply yet.
2. [Quote sent](pharmacy/02-quote-sent.html). Chats waiting for the client's reply.
3. [Accepted](pharmacy/03-accepted.html). Accepted orders, ready to prepare and deliver. A delivered order checks every status step, including the last one. After the client leaves a review, it replaces the client card in the right column and shows its date.
4. [Profile](pharmacy/04-profile.html). Business details, map visibility, and email notifications.
