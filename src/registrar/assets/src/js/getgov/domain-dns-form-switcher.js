class DNSFormSwitcherPartTwo{
    /**
     * Manages DNS form switching from Alpine Data
     * Requires an HTML container with Alpine.js initialized on it
     * 
     * State:
     * - pending: an object { type, recordId} representing the form the user is currently on
     *   type is either "edit" or "add", recordID is the form's recordID
     * - target: the form  ID the user is clicking to.
     * 
     * Methods
     * - attemptOpen: sets the pending object on the class instance
     * - switchForm: performs the actual form switch, and resets the pending and target
     *   - uses methods setShowId, and resetPendingAndTarget methods
     * - getAlpineData: returns the Alpine data object for the container
     *
    */ 
   
    constructor(container){
        this.pending = null;
        this.target = null;
        this.container = container;
    }

    setPending(value) {
         this.pending = value;
    }


    getAlpineData(){
        return Alpine.$data(this.container);
    }

    // setRecordtype(value){
    //     const data = this.getAlpineData();
    //     data.recordType = value;
    // }

    resetPendingAndTarget(){
       this.setTarget(null);
       this.setPending(null);
    }

    attemptOpen(form){
        this.setTarget(form);
        const currentId = this.getCurrentId();
        const req = {
            type: currentId > 0 ? "edit" : "add",
            recordId: currentId
        }
         this.setPending(req);
    }

}

class EditFormSwitcher extends DNSFormSwitcherPartTwo{

    setTarget(value){  
        const current = this.getAlpineData().showFormId;
        this.target = current == value ? null : value;
    }

    setShowId(value){
        const data = this.getAlpineData();
        data.showFormId = value;
    }

    getCurrentId(){
       return this.getAlpineData().showFormId;
    }
   
    switchForm(value = this.target){
       this.setShowId(value);
       this.resetPendingAndTarget();
    }

}