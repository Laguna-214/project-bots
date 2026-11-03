package app.projectbots;
/** Memory-only presentation bookkeeping; no backend business rules. */
final class DraftRevision {
 private long revision;
 void edited(){revision++;}
 long capture(){return revision;}
 boolean unchanged(long sent){return revision==sent;}
}
