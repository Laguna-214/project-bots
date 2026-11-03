package app.projectbots;
/** Generation, not an identity equality check: rejects selection ABA and logout races. */
final class SelectionGate {
 private long generation;
 synchronized long advance(){return ++generation;}
 synchronized long capture(){return generation;}
 synchronized boolean current(long captured){return generation==captured;}
}
